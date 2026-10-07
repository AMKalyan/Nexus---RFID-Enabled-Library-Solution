FROM python:3.12.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SIM_STATE_DIR=/state
WORKDIR /sim
COPY device-sim/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY device-sim/sim.py device-sim/panel.html ./
RUN useradd -r -u 10002 sim && mkdir -p /state && chown sim /state
USER sim
EXPOSE 8100
CMD ["python", "-c", "import sim, uvicorn; sim.panel(sim.Simulator(), 8100)"]
