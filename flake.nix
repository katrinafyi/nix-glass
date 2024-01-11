{
  description = "A very basic flake";

  # nixConfig.extra-substituters = [ "https://pac-nix.cachix.org/" ];
  # nixConfig.extra-trusted-public-keys = [ "pac-nix.cachix.org-1:l29Pc2zYR5yZyfSzk1v17uEZkhEw0gI4cXuOIsxIGpc=" ];

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;
      overlay = import ./overlay.nix;

      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      nixpkgss = lib.genAttrs systems
        (system: (import nixpkgs {
          system = system;
        }));

      forAllSystems' = f:
        lib.genAttrs
          systems
          (sys: f sys nixpkgss.${sys});

      forAllSystems = f: forAllSystems' (_: f);

      onlyDerivations = lib.filterAttrs (_: lib.isDerivation);

      makeAll = nixpkgs: pkgs':
        nixpkgs.symlinkJoin {
          name = "pac-nix-all";
          paths = lib.attrValues pkgs';
        };
    in
    {
      packages = forAllSystems (pkgs: {
        site = pkgs.callPackage ./site.nix { } { };
        main = pkgs.callPackage ./site.nix { } { site = /dev/null; };
        data = pkgs.callPackage ./datagen/package.nix { };
      });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
