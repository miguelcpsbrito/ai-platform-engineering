"""The same call through the platform SDK, printing the span it produced (Figure 8.3)."""
import pathlib
import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "observability"))
from platform_sdk import Context, Gateway  # noqa: E402

gw = Gateway(credential="lab-key-tenant-a", ctx=Context("tenant-a", "example"))
print(gw.chat([{"role": "user", "content": "Is water damage covered?"}]).text)
