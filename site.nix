{ runCommand
, zola
}:
{ site ? ./site }:
runCommand "nix-glass-site" { nativeBuildInputs = [ zola ]; }
  ''
    zola --root ${site} build -o $out
  ''
