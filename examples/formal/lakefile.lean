import Lake
open Lake DSL

package xi where
  leanOptions := #[⟨`autoImplicit, false⟩]

@[default_target]
lean_lib Xi where
  srcDir := "Xi"
