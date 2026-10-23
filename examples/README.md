# examples/

- `call_platform.py` — the platform contract from any language that speaks the OpenAI wire shape: here, the standard library.
- `sdk_traced_call.py` — the same call through the platform SDK, with the span printed.

Start the local gateway first: `make -C gateway serve`.
