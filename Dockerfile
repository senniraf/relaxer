FROM gurobi/python:10.0.0_3.9

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libgmp-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy
RUN pysmt-install --msat --confirm-agreement

COPY relaxer ./relaxer

ENTRYPOINT ["python", "-m", "relaxer"]
