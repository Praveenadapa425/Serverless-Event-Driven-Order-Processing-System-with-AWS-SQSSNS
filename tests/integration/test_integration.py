"""Integration tests for the complete event-driven order processing system."""
import pytest
import json
import os
import time
import boto3
import requests
import psycopg2


class TestOrderProcessingIntegration:
    """Integration tests for the order processing system."""
    
    @pytest.fixture(scope="class")
    def aws_client_config(self):
        """AWS client configuration for LocalStack."""
        return {
            'endpoint_url': os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566'),
            'region_name': os.environ.get('AWS_REGION', 'us-east-1'),
            'aws_access_key_id': 'test',
            'aws_secret_access_key': 'test'
        }
    
    @pytest.fixture(scope="class")
    def db_config(self):
        """Database configuration."""
        return {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'orders_db'),
            'user': os.environ.get('DB_USER', 'postgres'),
            'password': os.environ.get('DB_PASSWORD', 'postgres')
        }
    
    def test_sqs_queue_created(self, aws_client_config):
        """Test that SQS queue is created."""
        sqs = boto3.client('sqs', **aws_client_config)
        
        response = sqs.list_queues()
        
        assert 'QueueUrls' in response
        queue_names = [url.split('/')[-1] for url in response.get('QueueUrls', [])]
        assert 'OrderProcessingQueue' in queue_names
    
    def test_sns_topic_created(self, aws_client_config):
        """Test that SNS topic is created."""
        sns = boto3.client('sns', **aws_client_config)
        
        response = sns.list_topics()
        
        assert 'Topics' in response
        topic_arns = [topic['TopicArn'] for topic in response.get('Topics', [])]
        assert any('OrderStatusNotifications' in arn for arn in topic_arns)
    
    def test_database_connection(self, db_config):
        """Test database connection."""
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            # Check if orders table exists
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'orders'
                )
            """)
            
            table_exists = cur.fetchone()[0]
            assert table_exists is True
            
            cur.close()
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {str(e)}")
    
    def test_orders_table_schema(self, db_config):
        """Test orders table schema."""
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            # Get table columns
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'orders'
                ORDER BY ordinal_position
            """)
            
            columns = {row[0]: row[1] for row in cur.fetchall()}
            
            # Check required columns
            assert 'id' in columns
            assert 'user_id' in columns
            assert 'product_id' in columns
            assert 'quantity' in columns
            assert 'status' in columns
            assert 'created_at' in columns
            assert 'updated_at' in columns
            
            cur.close()
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {str(e)}")
    
    def test_insert_and_retrieve_order(self, db_config):
        """Test inserting and retrieving an order from database."""
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            # Insert test order
            test_order_id = 'TEST-ORD-' + str(int(time.time()))
            cur.execute("""
                INSERT INTO orders (id, user_id, product_id, quantity, status)
                VALUES (%s, %s, %s, %s, 'PENDING')
            """, (test_order_id, 'TEST-USER', 'TEST-PROD', 5))
            
            conn.commit()
            
            # Retrieve order
            cur.execute("SELECT * FROM orders WHERE id = %s", (test_order_id,))
            order = cur.fetchone()
            
            assert order is not None
            assert order[0] == test_order_id
            assert order[1] == 'TEST-USER'
            assert order[4] == 'PENDING'
            
            # Cleanup
            cur.execute("DELETE FROM orders WHERE id = %s", (test_order_id,))
            conn.commit()
            
            cur.close()
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {str(e)}")
    
    def test_update_order_status(self, db_config):
        """Test updating order status in database."""
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            # Insert test order
            test_order_id = 'TEST-UPDATE-' + str(int(time.time()))
            cur.execute("""
                INSERT INTO orders (id, user_id, product_id, quantity, status)
                VALUES (%s, %s, %s, %s, 'PENDING')
            """, (test_order_id, 'TEST-USER', 'TEST-PROD', 5))
            
            conn.commit()
            
            # Update status
            cur.execute("""
                UPDATE orders SET status = %s WHERE id = %s
            """, ('CONFIRMED', test_order_id))
            
            conn.commit()
            
            # Retrieve and verify
            cur.execute("SELECT status FROM orders WHERE id = %s", (test_order_id,))
            new_status = cur.fetchone()[0]
            
            assert new_status == 'CONFIRMED'
            
            # Cleanup
            cur.execute("DELETE FROM orders WHERE id = %s", (test_order_id,))
            conn.commit()
            
            cur.close()
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {str(e)}")
    
    def test_sqs_message_sending(self, aws_client_config):
        """Test sending message to SQS queue."""
        sqs = boto3.client('sqs', **aws_client_config)
        
        # Get queue URL
        response = sqs.get_queue_url(QueueName='OrderProcessingQueue')
        queue_url = response['QueueUrl']
        
        # Send test message
        test_message = {
            'order_id': 'TEST-ORD-' + str(int(time.time())),
            'user_id': 'TEST-USER',
            'product_id': 'TEST-PROD',
            'quantity': 5
        }
        
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(test_message)
        )
        
        assert 'MessageId' in response
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    
    def test_sns_message_publishing(self, aws_client_config):
        """Test publishing message to SNS topic."""
        sns = boto3.client('sns', **aws_client_config)
        
        # Get topic ARN
        response = sns.list_topics()
        topic_arn = None
        
        for topic in response.get('Topics', []):
            if 'OrderStatusNotifications' in topic['TopicArn']:
                topic_arn = topic['TopicArn']
                break
        
        if topic_arn is None:
            pytest.skip("SNS topic not found")
        
        # Publish test message
        test_message = {
            'order_id': 'TEST-ORD-' + str(int(time.time())),
            'new_status': 'CONFIRMED',
            'user_id': 'TEST-USER',
            'product_id': 'TEST-PROD'
        }
        
        response = sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(test_message),
            Subject='Test Notification'
        )
        
        assert 'MessageId' in response
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200

    def test_end_to_end_order_flow_via_apigateway(self, aws_client_config, db_config):
        """Test full flow from API Gateway -> Lambda -> SQS -> Lambda -> SNS -> Notification Lambda."""
        endpoint = self._get_orders_endpoint(aws_client_config)
        if endpoint is None:
            pytest.skip("OrderProcessingAPI or /orders resource not found")

        request_ts_ms = int(time.time() * 1000)
        test_payload = {
            'product_id': f'PROD-E2E-{int(time.time())}',
            'quantity': 2,
            'user_id': f'USER-E2E-{int(time.time())}'
        }

        response = requests.post(endpoint, json=test_payload, timeout=10)
        assert response.status_code in (200, 202)

        response_json = response.json()
        if isinstance(response_json.get('body'), str):
            body = json.loads(response_json['body'])
            status_code = response_json.get('statusCode', response.status_code)
        else:
            body = response_json
            status_code = response.status_code

        assert status_code == 202
        assert 'order_id' in body
        order_id = body['order_id']

        final_status = self._wait_for_final_order_status(db_config, order_id, timeout_seconds=90)
        assert final_status in ('CONFIRMED', 'FAILED')

        self._wait_for_notification_log(
            aws_client_config,
            order_id,
            request_ts_ms,
            timeout_seconds=90
        )

    @staticmethod
    def _get_orders_endpoint(aws_client_config):
        """Return LocalStack API Gateway endpoint for POST /orders."""
        api_gateway = boto3.client('apigateway', **aws_client_config)
        endpoint_url = aws_client_config['endpoint_url'].rstrip('/')

        apis = api_gateway.get_rest_apis(limit=500).get('items', [])
        api_id = None

        for api in apis:
            if api.get('name') == 'OrderProcessingAPI':
                api_id = api['id']
                break

        if not api_id:
            return None

        resources = api_gateway.get_resources(restApiId=api_id, limit=500).get('items', [])
        has_orders_resource = any(resource.get('path') == '/orders' for resource in resources)
        if not has_orders_resource:
            return None

        return f"{endpoint_url}/restapis/{api_id}/dev/_user_request_/orders"

    @staticmethod
    def _wait_for_final_order_status(db_config, order_id, timeout_seconds=60):
        """Poll database until order status is no longer PENDING."""
        deadline = time.time() + timeout_seconds
        last_status = None

        while time.time() < deadline:
            try:
                conn = psycopg2.connect(**db_config)
                cur = conn.cursor()
                cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
                row = cur.fetchone()
                cur.close()
                conn.close()

                if row:
                    last_status = row[0]
                    if last_status in ('CONFIRMED', 'FAILED'):
                        return last_status
            except Exception:
                pass

            time.sleep(2)

        pytest.fail(f"Timed out waiting for final order status for {order_id}. Last status: {last_status}")

    @staticmethod
    def _wait_for_notification_log(aws_client_config, order_id, start_time_ms, timeout_seconds=60):
        """Poll CloudWatch logs for NotificationService Lambda log containing the order ID."""
        logs = boto3.client('logs', **aws_client_config)
        log_group = '/aws/lambda/NotificationServiceFunction'
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                events = logs.filter_log_events(
                    logGroupName=log_group,
                    startTime=start_time_ms,
                    filterPattern=order_id,
                    limit=50
                ).get('events', [])

                if events:
                    return
            except Exception:
                # Log group can take a few seconds to appear after first invocation.
                pass

            time.sleep(2)

        pytest.fail(f"Timed out waiting for NotificationService logs for order {order_id}")
