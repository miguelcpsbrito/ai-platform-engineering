module hclfmt

go 1.22

require github.com/hashicorp/hcl/v2 v2.23.0

require (
	github.com/agext/levenshtein v1.2.1 // indirect
	github.com/apparentlymart/go-textseg/v13 v13.0.0 // indirect
	github.com/apparentlymart/go-textseg/v15 v15.0.0 // indirect
	github.com/google/go-cmp v0.6.0 // indirect
	github.com/mitchellh/go-wordwrap v0.0.0-20150314170334-ad45545899c7 // indirect
	github.com/zclconf/go-cty v1.13.0 // indirect
	golang.org/x/text v0.11.0 // indirect
)

replace golang.org/x/text => github.com/golang/text v0.21.0

replace golang.org/x/mod => github.com/golang/mod v0.22.0

replace golang.org/x/tools => github.com/golang/tools v0.28.0

replace golang.org/x/sync => github.com/golang/sync v0.10.0
