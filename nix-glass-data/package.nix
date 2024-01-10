{ lib
, python3Packages
}:
python3Packages.buildPythonApplication {
  pname = "nix-glass-data";
  version = "0.1.0";
  src = lib.cleanSource ./.;

  propagatedBuildInputs = with python3Packages; [ setuptools toml ];
  format = "pyproject";
}

