FROM public.ecr.aws/lambda/python:3.12

COPY src/order_creator_lambda/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/order_creator_lambda/app.py ${LAMBDA_TASK_ROOT}/app.py

CMD ["app.lambda_handler"]
