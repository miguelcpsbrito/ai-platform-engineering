package main

import (
	"bytes"
	"fmt"
	"os"

	"github.com/hashicorp/hcl/v2"
	"github.com/hashicorp/hcl/v2/hclsyntax"
	"github.com/hashicorp/hcl/v2/hclwrite"
)

// hclfmt -check|-write files...: the same canonical formatting terraform fmt applies.
func main() {
	mode := os.Args[1]
	bad := 0
	for _, f := range os.Args[2:] {
		src, _ := os.ReadFile(f)
		_, diags := hclsyntax.ParseConfig(src, f, hcl.Pos{Line: 1, Column: 1})
		if diags.HasErrors() {
			fmt.Println("SYNTAX", f, diags.Error())
			bad++
			continue
		}
		out := hclwrite.Format(src)
		if !bytes.Equal(src, out) {
			if mode == "-write" {
				os.WriteFile(f, out, 0644)
				fmt.Println("formatted", f)
			} else {
				fmt.Println("UNFORMATTED", f)
				bad++
			}
		}
	}
	if bad > 0 {
		os.Exit(1)
	}
}
