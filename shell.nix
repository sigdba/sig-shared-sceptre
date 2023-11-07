let
  nixpkgs = import <nixpkgs> {};
  # nix-dev = builtins.getFlake (toString ../nix-dev);
  nix-dev = builtins.getFlake "github:sigdba/nix-dev/90aa018";
in
nixpkgs.mkShell (
  nix-dev.shell.${builtins.currentSystem} {
    name = "SIG Shared Sceptre";
    aws = {
      enabled = true;
      profile = "sss";
    };
  }
)
