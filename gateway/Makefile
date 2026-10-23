# gateway/ build targets
PY ?= python3

.PHONY: package test serve render profiles

package:            ## Lambda package for the minimal platform's stub (Section 3.6)
	rm -rf build/package && mkdir -p build/package
	$(PY) -m pip install --quiet --target build/package --no-compile \
	  --platform manylinux2014_aarch64 --python-version 3.13 --only-binary=:all: "pyyaml>=6,<7"
	cp -r platform_gateway aliases.yaml settings.yaml prices.yaml build/package/
	cp -r tenants contracts env build/package/
	@echo "package ready: gateway/build/package"

test:
	$(PY) -m pytest -q tests

serve:              ## local platform API on :8080, simulated models
	$(PY) -m platform_gateway.server --mock --port 8080

render:             ## LiteLLM config for the proxy track (Section 4.5)
	$(PY) -m platform_gateway.render_litellm --env prod --out build/litellm \
	  $(if $(PROFILES),--profiles $(PROFILES),)

profiles:           ## the application profiles the alias map needs
	$(PY) -m platform_gateway.profiles --env $(or $(ENV),prod)
