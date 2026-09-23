package org.batfish.vendor.h3c.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.batfish.common.Warnings;
import org.batfish.config.Settings;
import org.batfish.datamodel.ConcreteInterfaceAddress;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.Prefix;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.vendor.h3c.representation.H3cConfiguration;
import org.junit.Test;

public final class H3cGrammarTest {
  @Test
  public void testSilentViewsAndReferences() {
    H3cCombinedParser parser =
        new H3cCombinedParser(
            """
            sysname r1
            qos policy OUTSIDE
             classifier ignored behavior ignored
            #
            ip vpn-instance blue
            #
            interface LoopBack0
             ip binding vpn-instance blue
             isis enable 10
            #
            """,
            new Settings());
    Warnings warnings = new Warnings(true, true, true);
    SilentSyntaxCollection silent = new SilentSyntaxCollection();
    H3cControlPlaneExtractor extractor = new H3cControlPlaneExtractor(parser, warnings, silent);
    extractor.processParseTree(null, parser.parse());
    H3cConfiguration vc = (H3cConfiguration) extractor.getVendorConfiguration();
    assertFalse(vc.getUnrecognized());
    assertEquals(1, silent.getElements().size());
    var structures = vc.getStructureManager();
    assertTrue(
        structures
            .getDefinition(org.batfish.vendor.h3c.representation.H3cStructureType.VPN, "blue")
            .isPresent());
    assertTrue(
        structures
            .getStructureReferences(org.batfish.vendor.h3c.representation.H3cStructureType.VPN)
            .containsKey("blue"));
    assertTrue(
        structures
            .getStructureReferences(org.batfish.vendor.h3c.representation.H3cStructureType.ISIS)
            .containsKey("10"));
  }

  @Test
  public void testFormatSerializationAndAdministrativeCosts() throws Exception {
    var format = org.batfish.datamodel.ConfigurationFormat.H3C_COMWARE;
    assertEquals(
        "\"h3c_comware\"", org.batfish.common.util.BatfishObjectMapper.writeString(format));
    assertEquals(
        format,
        org.batfish.common.util.BatfishObjectMapper.clone(
            format, org.batfish.datamodel.ConfigurationFormat.class));
    assertEquals(
        0, org.batfish.datamodel.RoutingProtocol.CONNECTED.getDefaultAdministrativeCost(format));
    assertEquals(
        60, org.batfish.datamodel.RoutingProtocol.STATIC.getDefaultAdministrativeCost(format));
    assertEquals(
        15, org.batfish.datamodel.RoutingProtocol.ISIS_L2.getDefaultAdministrativeCost(format));
    assertEquals(
        255, org.batfish.datamodel.RoutingProtocol.BGP.getDefaultAdministrativeCost(format));
    assertEquals(
        255, org.batfish.datamodel.RoutingProtocol.IBGP.getDefaultAdministrativeCost(format));
    assertEquals(
        1,
        org.batfish.datamodel.RoutingProtocol.STATIC.getDefaultAdministrativeCost(
            org.batfish.datamodel.ConfigurationFormat.CISCO_IOS));
  }

  static H3cConfiguration parse(String text) {
    H3cCombinedParser parser = new H3cCombinedParser(text, new Settings());
    Warnings warnings = new Warnings(true, true, true);
    H3cControlPlaneExtractor extractor =
        new H3cControlPlaneExtractor(parser, warnings, new SilentSyntaxCollection());
    extractor.processParseTree(null, parser.parse());
    assertTrue(parser.getErrors().toString(), parser.getErrors().isEmpty());
    H3cConfiguration vc = (H3cConfiguration) extractor.getVendorConfiguration();
    vc.setWarnings(warnings);
    vc.setFilename("h3c-test");
    return vc;
  }

  @Test
  public void testCaptureAndInterfacesAndStatic() throws Exception {
    H3cConfiguration vc =
        parse(
            """
            <r1>display current-configuration
            #
             version 7.1.075, ESS 8611
             sysname R1
            #
            ip vpn-instance blue
             route-distinguisher 65000:1
             address-family ipv4
              vpn-target 65000:1 both
            #
            interface LoopBack0
             ip address 10.0.0.1 255.255.255.255
            #
            interface Ten-GigabitEthernet1/0/1.100
             ip binding vpn-instance blue
             vlan-type dot1q vid 100
             ip address 192.0.2.1 255.255.255.252
            #
             ip route-static vpn-instance blue 203.0.113.0 24 NULL0 preference 75
             ip route-static 198.51.100.0 24 vpn-instance blue
            #
            return
            """);
    assertFalse(vc.getUnrecognized());
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals("r1", c.getHostname());
    assertEquals(
        ConcreteInterfaceAddress.parse("10.0.0.1/32"),
        c.getAllInterfaces().get("LoopBack0").getConcreteAddress());
    assertEquals("blue", c.getAllInterfaces().get("Ten-GigabitEthernet1/0/1.100").getVrfName());
    assertEquals(75, c.getVrfs().get("blue").getStaticRoutes().first().getAdministrativeCost());
    assertEquals(
        Prefix.parse("198.51.100.0/24"), c.getDefaultVrf().getStaticRoutes().first().getNetwork());
  }

  @Test
  public void testUnknownTargetIsNotSilentlyAccepted() {
    H3cConfiguration vc = parse("sysname r1\ninterface LoopBack0\n ip address-wrong 1.1.1.1\n#\n");
    assertTrue(vc.getUnrecognized());
    assertEquals(1, vc.getWarnings().getParseWarnings().size());
  }

  @Test
  public void testUnknownRetainedFamilyAndLocatorAreReported() {
    H3cConfiguration vc =
        parse(
            """
            sysname r1
            bgp 65000
             address-family l2vpn evpn
              peer 2001:db8::1 invented-command
            #
            segment-routing ipv6
             locator L ipv6-prefix 2001:db8:: 64
              invented-opcode
            #
            """);
    assertTrue(vc.getUnrecognized());
    assertEquals(2, vc.getWarnings().getParseWarnings().size());
  }

  @Test
  public void testMalformedPolicyFailsClosed() throws Exception {
    H3cConfiguration vc =
        parse("sysname r1\nroute-policy P permit node 10\n apply cost not-a-number\n#\n");
    assertTrue(vc.getUnrecognized());
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    var in =
        org.batfish.datamodel.Bgpv4Route.testBuilder()
            .setNetwork(Prefix.parse("192.0.2.0/24"))
            .build();
    assertFalse(
        c.getRoutingPolicies()
            .get("P")
            .process(
                in,
                in.toBuilder(),
                org.batfish.datamodel.routing_policy.Environment.Direction.OUT));
  }

  @Test
  public void testIncompletePolicyMatchFailsClosed() throws Exception {
    H3cConfiguration vc =
        parse("sysname r1\nroute-policy P permit node 10\n if-match community\n#\n");
    assertTrue(vc.getUnrecognized());
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    var in =
        org.batfish.datamodel.Bgpv4Route.testBuilder()
            .setNetwork(Prefix.parse("192.0.2.0/24"))
            .build();
    assertFalse(
        c.getRoutingPolicies()
            .get("P")
            .process(
                in,
                in.toBuilder(),
                org.batfish.datamodel.routing_policy.Environment.Direction.OUT));
  }

  @Test
  public void testMalformedBgpParameters() {
    for (String command :
        new String[] {
          "peer 192.0.2.2 enable ignored-tail",
          "peer 192.0.2.2 as-number 0",
          "peer 192.0.2.2 connect-interface LoopBack0 invalid-ip",
          "network 192.0.2.0 24 invented-option"
        }) {
      assertTrue(command, parse("sysname r1\nbgp 65000\n " + command + "\n#\n").getUnrecognized());
    }
  }

  @Test
  public void testIpv6OnlyIsisWarns() throws Exception {
    H3cConfiguration vc =
        parse(
            "sysname r1\n"
                + "isis 1\n"
                + " network-entity 49.0001.0000.0000.0001.00\n"
                + " address-family ipv6 unicast\n"
                + "#\n");
    vc.toVendorIndependentConfigurations();
    assertTrue(
        vc.getWarnings().getRedFlagWarnings().stream()
            .anyMatch(w -> w.getText().contains("IPv6 retained")));
  }

  @Test
  public void testMalformedInterfaceParameters() {
    for (String command :
        new String[] {
          "ip address 192.0.2.1 24 invented-option",
          "isis circuit-level invented",
          "isis circuit-type invented",
          "port link-mode invented",
          "ip address 192.0.2.1 33",
          "isis cost 44 level-2 ignored-tail"
        }) {
      H3cConfiguration vc =
          parse("sysname r1\ninterface GigabitEthernet1/0/1\n " + command + "\n#\n");
      assertTrue(command, vc.getUnrecognized());
    }
  }

  @Test
  public void testBridgeAggregation() throws Exception {
    H3cConfiguration vc =
        parse(
            """
            sysname r1
            interface Bridge-Aggregation1
             port link-type trunk
            #
            interface GigabitEthernet1/0/1
             port link-aggregation group 1
             port link-mode bridge
            #
            """);
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals(
        "Bridge-Aggregation1", c.getAllInterfaces().get("GigabitEthernet1/0/1").getChannelGroup());
    assertTrue(
        c.getAllInterfaces()
            .get("Bridge-Aggregation1")
            .getChannelGroupMembers()
            .contains("GigabitEthernet1/0/1"));
    assertTrue(c.getAllInterfaces().get("Bridge-Aggregation1").getSwitchport());
  }

  @Test
  public void testIsisSelectionAndBgp() throws Exception {
    H3cConfiguration vc =
        parse(
            """
            sysname r1
            router id 10.0.0.1
            interface LoopBack0
             ip address 10.0.0.1 32
             isis enable 10
            #
            interface GigabitEthernet1/0/1
             ip address 192.0.2.1 30
             isis enable 10
             isis circuit-type p2p
             isis cost 44
            #
            isis 10
             is-level level-2
             network-entity 49.0001.0000.0000.0001.00
             address-family ipv4 unicast
              import-route bgp
            #
            isis 100
             network-entity 49.0001.0000.0000.0100.00
             address-family ipv4 unicast
            #
            bgp 65001
             peer 192.0.2.2 as-number 65002
             address-family ipv4 unicast
              import-route direct
              peer 192.0.2.2 enable
            #
            """);
    assertFalse(vc.getUnrecognized());
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals(
        "49.0001.0000.0000.0001.00", c.getDefaultVrf().getIsisProcess().getNetAddress().toString());
    assertEquals(
        Long.valueOf(44),
        c.getAllInterfaces().get("GigabitEthernet1/0/1").getIsis().getLevel2().getCost());
    assertEquals(1, c.getDefaultVrf().getBgpProcess().getActiveNeighbors().size());
    assertEquals(255, c.getDefaultVrf().getBgpProcess().getEbgpAdminCost());
  }

  @Test
  public void testEvpnRetainedWithoutFabricatedVni() throws Exception {
    H3cConfiguration vc =
        parse(
            """
            sysname r1
            vsi blue
             evpn encapsulation srv6
              route-distinguisher 65000:1
              vpn-target 65000:1 both
              segment-routing ipv6 locator loc1
            #
            segment-routing ipv6
             locator loc1 ipv6-prefix 2001:db8:: 64 static 32
              opcode ::1 end-dt4 vpn-instance blue evpn
            #
            """);
    assertFalse(vc.getUnrecognized());
    assertEquals("srv6", vc.getVsis().get("blue").encapsulation);
    assertEquals("loc1", vc.getVsis().get("blue").locator);
    Configuration c = vc.toVendorIndependentConfigurations().get(0);
    assertTrue(c.getDefaultVrf().getLayer2Vnis().isEmpty());
    assertTrue(c.getDefaultVrf().getLayer3Vnis().isEmpty());
  }
}
