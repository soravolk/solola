FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy handler code
COPY handler.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["handler.lambda_handler"]
