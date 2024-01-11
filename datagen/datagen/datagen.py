#!/usr/bin/env python3
# vim: set ts=2 sw=2 sts=2 et: 

import os
import sys
import glob
import json
import toml
import shlex
import pathlib
import logging
import datetime
import argparse
import itertools
import subprocess

from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

def run(*args: str) -> str:
  log.debug(' $ ' +  ' '.join(map(shlex.quote, args)))
  return subprocess.check_output(args).decode('utf-8')

def nix(*args):
  return json.loads(run('nix', *args), object_hook=DotDict)

def rreplace(str, old, new):
  return new.join(str.rsplit(old, 1))

class DotDict(dict):
  __getattr__ = dict.__getitem__
  __setattr__ = dict.__setitem__ # type: ignore
  __delattr__ = dict.__delitem__ # type: ignore

@dataclass
class Derivation:
  attr: str = ''
  fullname: str = ''

  hash: str = ''
  path: str = ''
  pname: str = ''
  version: str = ''
  size: int = 0

  website: str = ''
  nixfile: str = ''
  upstream: str = ''

  builddepends: list[tuple[str,str]] = field(default_factory=list)
  rundepends: list[tuple[str,str]] = field(default_factory=list)
  requiredby: list[tuple[str,str]] = field(default_factory=list)
  outputs: dict[str, str] = field(default_factory=dict)

  shortdesc: str = ''
  longdesc: str = ''
  maintainers: list[str] = field(default_factory=list)

  files: list[tuple[str, str]] = field(default_factory=list)
  external: bool = True

Derivations = dict[str, Derivation] # hash -> derivation

@dataclass
class Flake:
  name: str
  fullname: str

  outputs: dict[str, list[Derivation]] = field(default_factory=dict)

  inputs: dict[str, str] = field(default_factory=dict) # input name -> url

def write_derivation(flakeout: str, time: int, drv: Derivation):
  # os.makedirs(flakeout, exist_ok=True)
  with open(flakeout + '/' + drv.hash + '.md', 'w') as f:
    f.write('+++\n')
    meta = DotDict()
    meta.title = drv.fullname
    meta.date = datetime.datetime.fromtimestamp(time)
    meta.description = drv.shortdesc
    meta.slug = drv.attr or drv.fullname
    meta.in_search_index = not drv.external
    meta.authors = drv.maintainers
    meta.extra = asdict(drv)
    toml.dump(meta, f)
    f.write('+++\n')

def main():
  logging.basicConfig(level=logging.DEBUG)

  argp = argparse.ArgumentParser(description="data generator for nix-glass.")
  argp.add_argument('flake', help='flake reference (required, e.g. github:nixos/nixpkgs)')
  argp.add_argument('output', nargs='?', help='output file (default: [flake].json)', default='')

  args = argp.parse_args()

  log.info(str(args))
  # os.makedirs(args.output, exist_ok=True)

  flakename = args.flake
  meta = nix('flake', 'metadata', '--json', flakename)
  f = Flake(meta['resolvedUrl'], meta['url'])
  log.debug(str(f))

  args.output = args.output or meta.resolved.repo + '.json'

  flakeshow = nix('flake', 'show', '--json', flakename)
  
  allderivations = {}
  
  def get(path):
    hash = path.split('/')[-1].split('-')[0]
    if hash in allderivations:
      return allderivations[hash] 
    d = Derivation('', rreplace(path.split('/')[-1].split('-', 1)[1], '.drv', ''), hash, path)
    allderivations[hash] = d
    return d

  def rundepend(path):
    drv = nix('path-info', path, '--json')[0].deriver
    (_, drvshow), = nix('derivation', 'show', drv).items()
    out = [x for x,v in drvshow.outputs.items() if v.path == path]
    return (drv, out[0])

  for outputtype, values in flakeshow.items():
    values2 = values.items()
    if 'x86_64-linux' in values.keys() and 'type' not in values['x86_64-linux']:
      values2 = itertools.chain(*(x.items() for x in values.values()))
    values2 = filter(lambda x: x[1].get('type') == 'derivation', values2)

    f.outputs[outputtype] = thisoutput = []

    for attr, drv in values2:
      if attr != 'asli': continue
      arg = f.fullname + '#' + attr
      (path, drvshow), = nix('derivation', 'show', arg).items()

      drvmeta = nix('eval', arg + '.meta', '--json')
      try:
        src = str(nix('eval', arg + '.src.url', '--json'))
      except subprocess.CalledProcessError:
        src = ''

      d = get(path)
      thisoutput.append(d)
      d.external = False
      d.attr = attr
      d.pname = drvshow.env.get('pname') or drvshow.env.name
      d.version = drvshow.env.get('version') or ''

      d.upstream = src
      d.website = drvmeta.get('homepage') or ''
      d.shortdesc = drvmeta.get('description') or ''
      d.longdesc = drvmeta.get('longDescription') or ''

      built = nix('build', arg, '--json')[0]

      info = nix('path-info', arg, '--json', '--closure-size')[0]

      d.size = info.closureSize
      d.rundepends = [ rundepend(ref) for ref in info.references ]
      
      for oname, opath in drvshow.outputs.items():
        d.outputs[oname] = opath.path

      builtpath = list(built.outputs.values())[0]
      for root, dirs, files in os.walk(builtpath):
        links = [d for d in dirs if os.path.islink(os.path.join(root, d))]
        # d.files.append((root.replace(builtpath + '/', '') + '/', ''))
        for fi in links + files:
          f2 = os.path.join(root, fi)
          dest = ''
          if os.path.islink(f2):
            dest = os.readlink(f2)
          d.files.append((f2.replace(builtpath + '/', ''), dest))

      for d, x in drvshow.inputDrvs.items():
        outs = x
        for out in drvshow.outputs:
          get(d).requiredby.append((path, out))
        for out in outs:
          get(path).builddepends.append((d, out))

  # pprint(asdict(f))
  log.info('writing to ' + args.output)
  with open(args.output, 'w') as file:
    json.dump(asdict(f), file)


  
  
  

