# Repository entry points. CI runs `make test labs-local tf-offline`.
PY ?= python3
TF_DIRS := org network network/hub identity gateway/terraform/stub \
           gateway/terraform/proxy/cluster gateway/terraform/proxy/app tenancy/terraform/registry \
           tenancy/terraform/baseline tenancy/terraform/vector-index finops/terraform \
           governance/guardrails labs/ch03/org labs/ch03/platform

.PHONY: test labs-local tf-offline tf-validate fmt

test:                 ## every offline suite
	$(PY) -m pytest -q org/tests gateway/tests tenancy/tests finops/tests observability/tests \
	  governance/tests agents/tests tests/conformance tests/restore tests/scp
	$(PY) -m pytest -q -p no:cacheprovider tests/leakage

labs-local:           ## local tracks of the labs (no AWS)
	$(PY) labs/ch04/prove_local.py
	$(PY) labs/ch06/run_local.py
	$(PY) labs/ch07/walk_local.py
	$(PY) labs/ch08/flip_local.py
	$(PY) labs/ch09/gameday_local.py
	$(PY) labs/ch10/run_local.py
	$(PY) labs/ch12/drill_local.py

tools/aws_schema.json:  ## AWS provider 6.x argument schema, from the cdktf bindings (offline checks)
	cd tools && npm install --no-save --ignore-scripts @cdktf/provider-aws@21 >/dev/null && \
	  $(PY) tfschema.py node_modules/@cdktf/provider-aws/.jsii aws_schema.json

tf-offline: tools/aws_schema.json  ## HCL syntax + provider schema + undeclared references, no binary needed
	# gateway/terraform/profiles is checked too; terraform validate covers it through labs/ch03/platform
	$(PY) tools/tfcheck.py tools/aws_schema.json $(TF_DIRS) gateway/terraform/profiles

tf-validate:          ## the real thing: terraform init/validate per module
	@for d in $(TF_DIRS); do echo "== $$d"; terraform -chdir=$$d init -backend=false -input=false >/dev/null && \
	  terraform -chdir=$$d validate || exit 1; done

fmt:
	terraform fmt -recursive -check -diff -list=true . || \
	  (cd tools/hclfmt && go build -o hclfmt . && cd ../.. && \
	   tools/hclfmt/hclfmt -check $$(find . -name '*.tf' -not -path '*/skeleton/*' -not -path '*/.terraform/*'))
