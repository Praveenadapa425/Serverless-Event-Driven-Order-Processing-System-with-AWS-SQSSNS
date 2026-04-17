FROM public.ecr.aws/lambda/python:3.12

COPY src/notification_service_lambda/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/notification_service_lambda/app.py ${LAMBDA_TASK_ROOT}/app.py

CMD ["app.lambda_handler"]
