FROM public.ecr.aws/lambda/python:3.9

# Copy requirements and install dependencies into Lambda task root.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy Lambda function code.
COPY src/order_creator_lambda/app.py ${LAMBDA_TASK_ROOT}/app.py
COPY src/shared/ ${LAMBDA_TASK_ROOT}/shared/

# Set the Lambda handler.
CMD ["app.lambda_handler"]
