import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def init_telemetry(app, service_name="walkbuddy-backend"):
    """
    Initializes OpenTelemetry with OTLP exporter to Jaeger.
    Compatible with: docker-compose.jaeger.yml (ports: 4317:4317)
    """
    
    # 1. Define the Resource (Service Name)
    resource = Resource.create(attributes={
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "development"
    })

    # 2. Configure the Tracer Provider
    tracer_provider = TracerProvider(resource=resource)
    
    # 3. Configure the Exporter (Sends data to Jaeger via OTLP gRPC)
    # Since you are running the backend on localhost and Jaeger in Docker exposing port 4317,
    # localhost:4317 is the correct endpoint.
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317", 
        insecure=True
    )
    
    # Use BatchProcessor for better performance (sends traces in chunks)
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # 4. Set the Global Tracer Provider
    # This allows 'trace.get_tracer()' to work in other files
    trace.set_tracer_provider(tracer_provider)

    # 5. Auto-Instrument HTTPX (Captures LibriVox & OSRM calls automatically)
    HTTPXClientInstrumentor().instrument()

    # 6. Instrument FastAPI
    # This captures all incoming HTTP requests to your API
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    
    print(f"[Telemetry] OTel initialized for {service_name} -> http://localhost:4317")