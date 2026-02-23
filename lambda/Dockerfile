# Lambda container image for Python 3.10 on Amazon Linux 2023
# Docs: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
FROM public.ecr.aws/lambda/python:3.10

# Install build tools required for compiling native Python packages
# (h5py, llvmlite, sentencepiece, scikit-learn, etc.)
# Also install libsndfile for librosa audio loading
RUN yum -y install \
    gcc gcc-c++ make \
    cmake3 \
    pkg-config \
    hdf5-devel \
    libffi-devel \
    libsndfile \
    tar xz \
 && ln -sf /usr/bin/cmake3 /usr/bin/cmake \
 && yum clean all

# Install ffmpeg static build for MP3/other format support
RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz \
 && tar -xf /tmp/ffmpeg.tar.xz -C /tmp \
 && mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
 && mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
 && rm -rf /tmp/ffmpeg* \
 && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Copy function code into the Lambda task root
# Everything under this directory becomes available to your Lambda at /var/task
COPY . /var/task/

# Install Python dependencies from requirements.txt
# Torch CPU wheels will be pulled from PyTorch index by --extra-index-url
RUN python -m pip install --upgrade pip \
        && python -m pip install --no-cache-dir -r /var/task/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# (Optional) If model checkpoints are large, consider removing them from the image
# and download from S3 to /tmp at cold start for faster deploys and smaller image.
# Otherwise, ensure the paths in handler.py/inference.py match /var/task locations.

# Set the Lambda handler: module.function
# Your handler file is handler.py and entry function is lambda_handler
CMD [ "handler.lambda_handler" ]
