#!/usr/bin/python
# -*- python-indent: 2; py-indent-offset: 2 -*-
# Copyright 2009 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
"""Debmarshal distribution class for Ubuntu images."""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import os
import shutil
import subprocess
import tempfile

import decorator

from debmarshal.distros import base


def _stopInitScripts(target):
  """Stop init scripts from running.

  This function, along with _startInitScripts, primarily exists to
  allow for more easily mocking out the withoutInitScripts decorator
  in testing.

  Args:
    target: The root of the filesystem where we're stopping init
      scripts.
  """
  policy_path = os.path.join(target, 'usr/sbin/policy-rc.d')
  policy = open(policy_path, 'w')
  policy.write("#!/bin/sh\n"
               "exit 101\n")
  policy.close()

  os.chmod(policy_path, 0755)


def _startInitScripts(target):
  """Allow init scripts to write.

  This function, along with _stopInitScripts, primarily exists to
  allow for more easily mocking out the withoutInitScripts decorator
  in testing.

  Args:
    target: The root of the filesystem where we're allowing init
      scripts.
  """
  policy_path = os.path.join(target, 'usr/sbin/policy-rc.d')
  if os.path.exists(policy_path):
    os.remove(policy_path)


@decorator.decorator
def withoutInitScripts(f, *args, **kwargs):
  """Decorator to disable init scripts in a chroot.

  Functions decorated with withoutInitScripts have a policy.rc-d file
  created in order to prevent any Ubuntu Policy-compliant init scripts
  from running.

  This decorator is designed for use with class methods, and assumes
  that the object being operated on has a target attribute with the
  root of the disk image.
  """
  self = args[0]
  _stopInitScripts(self.target)

  try:
    f(*args, **kwargs)
  finally:
    _startInitScripts(self.target)


class Ubuntu(base.Distribution):
  """Ubuntu (and Ubuntu-based) distributions."""
  base_defaults = {'mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'security_mirror': 'http://security.ubuntu.com/ubuntu/',
                   'updates_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'backports_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'proposed_mirror': 'http://us.archive.ubuntu.com/ubuntu/',
                   'enable_security': True,
                   'enable_updates': True,
                   'enable_backports': False,
                   'enable_proposed': False,
                   'keyring': '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
                   'arch': 'amd64',
                   'suite': 'jaunty',
                   'components': ['main', 'restricted', 'universe', 'multiverse']
                   }

  base_configurable = set(['arch', 'suite', 'components', 'enable_security',
                           'enable_updates', 'enable_backports',
                           'enable_proposed'])

  custom_defaults = {'add_pkg': [],
                     'rm_pkg': [],
                     'ssh_key': '',
                     'kernel': 'linux-image-generic',
                     # Configuration for networking doesn't really
                     # fit well into this config model. But if dhcp
                     # is True, then ip, netmask, gateway, and dns
                     # should have their default values. If dhcp is
                     # False, then they should all be set.
                     'dhcp': True,
                     'ip': None,
                     'netmask': None,
                     'gateway': None,
                     'dns': [],
                     }

  custom_configurable = set(['add_pkg', 'rm_pkg', 'ssh_key', 'kernel',
                             'hostname', 'domain',
                             'dhcp', 'ip', 'netmask', 'gateway', 'dns'])

  def _mountImage(self, img):
    """Mount a filesystem image in a temporary directory.

    This method handles safely creating a location to mount an
    image. It is the responsibility of the caller to unmount an
    image. The use of _umountImage is recommended for handling this.

    Args:
      img: A filesystem image file.

    Returns:
      The root of the mounted filesystem.
    """
    root = tempfile.mkdtemp()
    try:
      base.captureCall(['mount', '-o', 'loop', img, root])
    except:
      os.rmdir(root)
      raise
    return root

  def _umountImage(self, root):
    """Clean up a temporarily mounted filesystem image.

    This method handles cleaning up after _mountImage.

    Args:
      root: The root of the temporary filesystem; the return value
        from _mountImage
    """
    base.captureCall(['umount', '-l', root])

    os.rmdir(root)

  def _verifyImage(self, image):
    """Verify that some disk image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    This method is used for verifying both base and customized images.

    Args:
      image: The disk image file to verify.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    root = self._mountImage(image)

    try:
      try:
        base.captureCall(['chroot', root,
                          'apt-get',
                          '-qq',
                          'update'])

        # apt-get -sqq dist-upgrade will print out a summary of the
        # steps it would have taken, had this not been a dry run. If
        # there is nothing to do, it will print nothing.
        updates = base.captureCall(['chroot', root,
                                    'apt-get',
                                    '-o', 'Debug::NoLocking=true',
                                    '-sqq',
                                    'dist-upgrade'])
        return updates.strip() == ''
      except subprocess.CalledProcessError:
        return False
    finally:
      self._umountImage(root)

  def verifyBase(self):
    """Verify that a base image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    if not super(Ubuntu, self).verifyBase():
      return False
    else:
      return self._verifyImage(self.basePath())

  def verifyCustom(self):
    """Verify that a customized image is still valid.

    For Ubuntu images, this means verifying that there are no pending
    package updates.

    Returns:
      A bool. True if the image is valid; False if it's not.
    """
    if not super(Ubuntu, self).verifyCustom():
      return False
    else:
      return self._verifyImage(self.customPath())

  def _createSparseFile(self, path, len):
    """Create a sparse file.

    Create a sparse file with a given length, say for use as a disk
    image.

    It is the caller's responsibility to ensure that the passed in
    path doesn't exist, or can be overwritten.

    Args:
      path: Path to the file to be created.
      len: Length of the sparse file in bytes.
    """
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
      os.makedirs(dir)
    open(path, 'w').truncate(len)

  def _runInTarget(self, command_args, *args, **kwargs):
    """Run a command in the install target.

    All extra positional and keyword arguments are passed on to
    captureCall.

    Args:
      command_args: The command and arguments to run within the
        target.
    """
    chroot_args = ['chroot', self.target]
    chroot_args.extend(command_args)
    return base.captureCall(chroot_args, *args, **kwargs)

  def _installFilesystem(self, path):
    """Create an ext3 filesystem in the device at path.

    path may be a file or a block device.

    Args:
      path: Path to the block device where a filesystem should be
        created.
    """
    base.captureCall(['mkfs', '-t', 'ext3', '-F', path])

  @withoutInitScripts
  def _installPackages(self, *pkgs):
    """Install a series of packages in a chroot.

    Args:
      pkgs: The list of packages to install.
    """
    env = dict(os.environ)
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    args = ['apt-get', '-y', 'install']
    args.extend(pkgs)
    self._runInTarget(args, env=env)

  @withoutInitScripts
  def _installReconfigure(self, pkg):
    """Reconfigure a package within a chroot.

    Args:
      pkg: The package to reconfigure.
    """
    self._runInTarget(['dpkg-reconfigure',
                       '-fnoninteractive',
                       '-pcritical',
                       pkg])

  def _installDebootstrap(self):
    """Debootstrap a basic Ubuntu install."""
    components = ','.join(self.getBaseConfig('components'))
    base.captureCall(['debootstrap',
                      '--keyring=%s' % self.getBaseConfig('keyring'),
                      '--arch=%s' % self.getBaseConfig('arch'),
                      '--components=%s' % components,
                      self.getBaseConfig('suite'),
                      self.target,
                      self.getBaseConfig('mirror')])

  def _installHosts(self):
    """Install the /etc/hosts file."""
    hosts = open(os.path.join(self.target, 'etc/hosts'), 'w')
    hosts.write("127.0.0.1 localhost\n"
                "\n"
                "# The following lines are desirable for IPv6 capable hosts\n"
                "::1 ip6-localhost ip6-loopback\n"
                "fe00::0 ip6-localnet\n"
                "ff00::0 ip6-mcastprefix\n"
                "ff02::1 ip6-allnodes\n"
                "ff02::2 ip6-allrouters\n"
                "ff02::3 ip6-allhosts\n")
    hosts.close()

  def _installSources(self):
    """Install the sources.list file."""
    sources = open(os.path.join(self.target, 'etc/apt/sources.list'), 'w')

    try:
      sources_conf = [
          self.getBaseConfig('mirror'),
          self.getBaseConfig('suite'),
          ' '.join(self.getBaseConfig('components'))]
      sources.write('deb %s %s %s\n' % tuple(sources_conf))
      sources.write('deb-src %s %s %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_security'):
        sources_conf[0] = self.getBaseConfig('security_mirror')
        sources.write('deb %s %s-security %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-security %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_updates'):
        sources_conf[0] = self.getBaseConfig('updates_mirror')
        sources.write('deb %s %s-updates %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-updates %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_backports'):
        sources_conf[0] = self.getBaseConfig('backports_mirror')
        sources.write('deb %s %s-backports %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-backports %s\n' % tuple(sources_conf))

      if self.getBaseConfig('enable_proposed'):
        sources_conf[0] = self.getBaseConfig('proposed_mirror')
        sources.write('deb %s %s-proposed %s\n' % tuple(sources_conf))
        sources.write('deb-src %s %s-proposed %s\n' % tuple(sources_conf))
    finally:
      sources.close()

  @withoutInitScripts
  def _installUpdates(self):
    """Take all pending updates."""
    self._runInTarget(['apt-get',
                       'update'])
    self._runInTarget(['apt-get',
                       '-y',
                       'dist-upgrade'])

  @withoutInitScripts
  def _installLocale(self):
    """Configure locale settings."""
    locale = open(os.path.join(self.target, 'etc/default/locale'), 'w')
    locale.write('LANG="en_US.UTF-8"\n')
    locale.close()

    locale_gen = open(os.path.join(self.target, 'etc/locale.gen'), 'w')
    locale_gen.write('en_US.UTF-8 UTF-8\n')
    locale_gen.close()

    self._installPackages('locales')

    self._runInTarget(['locale-gen'])
    self._installReconfigure('locales')

  @withoutInitScripts
  def _installTimezone(self):
    """Configure timezone settings."""
    timezone = open(os.path.join(self.target, 'etc/timezone'), 'w')
    timezone.write('America/Los_Angeles\n')
    timezone.close()

    self._installReconfigure('tzdata')

  def _installPartitions(self, img):
    """Partition a disk image.

    Right now, the disk is broken into a Linux partition, followed by
    a 1G swap partition. All remaining space past that 1G is allocated
    to the Linux partition.

    Args:
      img: Path to the image file to partition.
    """
    # TODO(ebroder): Allow for more arbitrary partitioning

    # This is slightly braindead math, but I don't really care about
    # the swap partition being /exactly/ 1G.
    disk_blocks = os.stat(img).st_size / (1024 ** 2)
    swap_blocks = 1024
    root_blocks = disk_blocks - swap_blocks

    base.captureCall(
        ['sfdisk', '-uM', img],
        stdin_str=',%d,L,*\n,,S\n;\n;\n' % root_blocks)

  def createBase(self):
    """Create a valid base image.

    This method is responsible for creating a base image at
    self.basePath().

    No arguments are taken and no value is returned, because the
    location of the resulting base image is already known.
    """
    if self.verifyBase():
      return

    if os.path.exists(self.basePath()):
      os.remove(self.basePath())

    self._createSparseFile(self.basePath(), 1024 ** 3)
    try:
      self._installFilesystem(self.basePath())
      self.target = self._mountImage(self.basePath())

      try:
        self._installDebootstrap()
        self._installHosts()
        self._installSources()
        self._installUpdates()
        self._installLocale()
        self._installTimezone()
      finally:
        self._umountImage(self.target)
    except:
      os.remove(self.basePath())
      raise