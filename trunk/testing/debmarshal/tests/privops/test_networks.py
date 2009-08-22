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
"""tests for the debmarshal privileged networking module"""


__authors__ = [
    'Evan Broder <ebroder@google.com>',
]


import unittest

import mox
import libvirt
from lxml import etree

from debmarshal import errors
from debmarshal._privops import networks
from debmarshal._privops import utils
import debmarshal.utils


class TestListBridges(mox.MoxTestBase):
  def test(self):
    self.mox.StubOutWithMock(debmarshal.utils, 'captureCall')
    debmarshal.utils.captureCall(['brctl', 'show']).AndReturn(
      'bridge name\tbridge id\t\tSTP enabled\tinterfaces\n'
      'pan0\t\t8000.000000000000\tno\t\t\n')

    self.mox.ReplayAll()

    self.assertEqual(list(networks._listBridges()), ['pan0'])


class TestValidateHostname(mox.MoxTestBase):
  """Test debmarshal._privops.networks._validateHostname"""
  def testInvalidInput(self):
    """Make sure that an exception gets raised if an invalid hostname
    is passed in"""
    self.assertRaises(errors.InvalidInput, networks._validateHostname,
                      'not-a-domain.#$@')

  def testValidInput(self):
    """Test that nothing happens if a valid hostname is passed in"""
    # Unfortunately unittest.TestCase doesn't have any built-in
    # mechanisms to mark raised exceptions as a failure instead of an
    # error, but an error seems good enough
    networks._validateHostname('real-hostname.com')


class TestLoadNetworkState(mox.MoxTestBase):
  """Test loading the network state from /var/run/debmarshal-networks"""
  def testOpeningLibvirtConnection(self):
    """Make sure that loadNetworkState can open its own connection to
    libvirt if needed"""
    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(None)

    self.mox.StubOutWithMock(libvirt, 'open')
    virt_con = self.mox.CreateMock(libvirt.virConnect)
    libvirt.open(mox.IgnoreArg()).AndReturn(virt_con)

    self.mox.ReplayAll()

    self.assertEqual(networks.loadNetworkState(), {})

  def testNetworkExistenceTest(self):
    """Make sure that networks get dropped from the list in the state
    file if they don't still exist. And that they're kept if they do"""
    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(
      {'foo': 500,
       'bar': 501})

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    virt_con.networkLookupByName('foo').InAnyOrder()
    virt_con.networkLookupByName('bar').InAnyOrder().AndRaise(
        libvirt.libvirtError("Network doesn't exist"))

    self.mox.ReplayAll()

    self.assertEqual(networks.loadNetworkState(virt_con),
                     {'foo': 500})

  def testTwoBadNetworks(self):
    """Test finding two nonexistent networks when loading state."""
    nets = {'foo': 500,
            'bar': 500,
            'baz': 500,
            'quux': 500,
            'spam': 500,
            'eggs': 500}

    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    self.mox.StubOutWithMock(utils, 'loadState')
    utils.loadState('debmarshal-networks').AndReturn(dict(nets))

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    virt_con.networkLookupByName('foo').InAnyOrder()
    virt_con.networkLookupByName('bar').InAnyOrder()
    virt_con.networkLookupByName('baz').InAnyOrder().AndRaise(
        libvirt.libvirtError("Network doens't exist"))
    virt_con.networkLookupByName('quux').InAnyOrder()
    virt_con.networkLookupByName('spam').InAnyOrder().AndRaise(
        libvirt.libvirtError("Network doesn't exist"))
    virt_con.networkLookupByName('eggs').InAnyOrder()

    self.mox.ReplayAll()

    del nets['baz']
    del nets['spam']

    self.assertEqual(networks.loadNetworkState(virt_con),
                     nets)


class TestNetworkBounds(mox.MoxTestBase):
  """Test converting a gateway/netmask to the low and high IP
  addresses in the network"""
  def test24(self):
    """Test a converting a /24 network, what debmarshal uses"""
    self.assertEqual(networks._networkBounds('192.168.1.1', '255.255.255.0'),
                     ('192.168.1.2', '192.168.1.254'))


class TestGenNetworkXML(mox.MoxTestBase):
  """Test the XML generated by networks._genNetworkXML"""
  name = 'debmarshal-1'
  net = '169.254.4'
  gateway = '%s.1' % net
  netmask = '255.255.255.0'
  hosts = {'wiki.company.com': ('169.254.4.2', 'AA:BB:CC:DD:EE:FF'),
           'login.company.com': ('169.254.4.3', '00:11:22:33:44:55')}

  def testXml(self):
    """Test an XML tree."""
    xml_string = networks._genNetworkXML(self.name,
                                        self.gateway,
                                        self.netmask,
                                        self.hosts)
    xml = etree.fromstring(xml_string)

    # These assertions are simply used to test that the element with
    # the right name exists
    self.assertNotEqual(xml.xpath('/network'), [])

    self.assertNotEqual(xml.xpath('/network/name'), [])
    self.assertEqual(xml.xpath('string(/network/name)'), self.name)

    self.assertNotEqual(xml.xpath('/network/ip'), [])
    self.assertEqual(xml.xpath('string(/network/ip/@address)'), self.gateway)
    self.assertEqual(xml.xpath('string(/network/ip/@netmask)'), self.netmask)

    self.assertNotEqual(xml.xpath('/network/ip/dhcp'), [])

    self.assertNotEqual(xml.xpath('/network/ip/dhcp/range'), [])
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@start)'),
                     '%s.2' % self.net)
    self.assertEqual(xml.xpath('string(/network/ip/dhcp/range/@end)'),
                     '%s.254' % self.net)

    self.assertEqual(len(xml.xpath('/network/ip/dhcp/host')), len(self.hosts))
    for h, hinfo in self.hosts.iteritems():
      host_node = '/network/ip/dhcp/host[@name = $name]'
      self.assertNotEqual(xml.xpath(host_node, name=h), [])
      self.assertEqual(xml.xpath('string(%s/@ip)' % host_node, name=h), hinfo[0])
      self.assertEqual(xml.xpath('string(%s/@mac)' % host_node, name=h), hinfo[1])


class TestFindUnusedName(mox.MoxTestBase):
  """Test privops.networks._findUnusedName."""
  def test(self):
    virt_con = self.mox.CreateMock(libvirt.virConnect)

    self.mox.StubOutWithMock(utils, '_clearLibvirtError')
    utils._clearLibvirtError()

    name = 'debmarshal-0'
    virt_con.networkLookupByName(name)

    name = 'debmarshal-1'
    virt_con.networkLookupByName(name).AndRaise(libvirt.libvirtError(
      "Network doesn't exist."))

    self.mox.ReplayAll()

    self.assertEqual(networks._findUnusedName(virt_con), name)


class TestFindUnusedNetwork(mox.MoxTestBase):
  def testSuccessfulFind(self):
    """Test privops.networks._findUnusedNetwork finding an available network"""
    nets = ['default', 'debmarshal-0', 'debmarshal-3']

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    virt_con.listNetworks().AndReturn(nets)
    virt_con.listDefinedNetworks().AndReturn([])

    for i, net in enumerate(nets):
      virt_net = self.mox.CreateMock(libvirt.virNetwork)
      virt_con.networkLookupByName(net).AndReturn(virt_net)
      virt_net.XMLDesc(0).AndReturn(
        '<network>' +
        ('<ip address="169.254.%s.1" netmask="255.255.255.0" />' % i) +
        '</network>')

    self.mox.ReplayAll()

    self.assertEqual(networks._findUnusedNetwork(virt_con, 8),
                     ('169.254.3.1', '255.255.255.0'))

  def testNoFind(self):
    """privops.networks_findUnusedNetwork errors when no network available"""
    nets = ['debmarshal-%s' % i for i in xrange(256)]

    virt_con = self.mox.CreateMock(libvirt.virConnect)

    virt_con.listNetworks().AndReturn(nets)
    virt_con.listDefinedNetworks().AndReturn([])

    for i, net in enumerate(nets):
      virt_net = self.mox.CreateMock(libvirt.virNetwork)
      virt_con.networkLookupByName(net).AndReturn(virt_net)
      virt_net.XMLDesc(0).AndReturn(
        '<network>' +
        ('<ip address="169.254.%s.1" netmask="255.255.255.0" />' % i) +
        '</network>')

    self.mox.ReplayAll()

    self.assertRaises(errors.NoAvailableIPs, networks._findUnusedNetwork,
                      virt_con, 8)


if __name__ == '__main__':
  unittest.main()
