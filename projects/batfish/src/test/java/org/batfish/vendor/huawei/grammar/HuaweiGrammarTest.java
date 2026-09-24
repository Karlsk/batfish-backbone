package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.batfish.common.Warnings;
import org.batfish.config.Settings;
import org.batfish.datamodel.Ip;
import org.batfish.grammar.silent_syntax.SilentSyntaxCollection;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;
import org.junit.Test;

public final class HuaweiGrammarTest {
  @Test
  public void testFormatSerializationAndDistances() throws Exception {
    var format = org.batfish.datamodel.ConfigurationFormat.HUAWEI_VRP;
    assertEquals("\"huawei_vrp\"", org.batfish.common.util.BatfishObjectMapper.writeString(format));
    assertEquals(
        format,
        org.batfish.common.util.BatfishObjectMapper.clone(
            format, org.batfish.datamodel.ConfigurationFormat.class));
    assertEquals(
        0, org.batfish.datamodel.RoutingProtocol.CONNECTED.getDefaultAdministrativeCost(format));
    assertEquals(
        0, org.batfish.datamodel.RoutingProtocol.LOCAL.getDefaultAdministrativeCost(format));
    assertEquals(
        60, org.batfish.datamodel.RoutingProtocol.STATIC.getDefaultAdministrativeCost(format));
    assertEquals(
        15, org.batfish.datamodel.RoutingProtocol.ISIS_L2.getDefaultAdministrativeCost(format));
    assertEquals(
        255, org.batfish.datamodel.RoutingProtocol.BGP.getDefaultAdministrativeCost(format));
    assertEquals(
        255, org.batfish.datamodel.RoutingProtocol.IBGP.getDefaultAdministrativeCost(format));
    assertEquals(
        255, org.batfish.datamodel.RoutingProtocol.AGGREGATE.getDefaultAdministrativeCost(format));
    assertEquals(
        1,
        org.batfish.datamodel.RoutingProtocol.STATIC.getDefaultAdministrativeCost(
            org.batfish.datamodel.ConfigurationFormat.CISCO_IOS));
  }

  static HuaweiConfiguration parse(String text) {
    HuaweiCombinedParser parser = new HuaweiCombinedParser(text, new Settings());
    Warnings warnings = new Warnings(true, true, true);
    HuaweiControlPlaneExtractor extractor =
        new HuaweiControlPlaneExtractor(parser, warnings, new SilentSyntaxCollection());
    extractor.processParseTree(null, parser.parse());
    assertTrue(parser.getErrors().toString(), parser.getErrors().isEmpty());
    HuaweiConfiguration vc = (HuaweiConfiguration) extractor.getVendorConfiguration();
    vc.setWarnings(warnings);
    vc.setFilename("huawei-test");
    return vc;
  }

  @Test
  public void testAfInheritanceAndDefaultActivation() {
    var vc =
        parse(
            """
            sysname r2
            ip vpn-instance blue
             ipv4-family
            #
            bgp 65000
             router-id 10.0.0.1
             group CLIENT internal
             peer CLIENT advertise-community
             peer 10.0.0.2 group CLIENT
             peer 10.0.0.3 as-number 65001
             ipv4-family unicast
              undo peer CLIENT enable
              peer 10.0.0.2 enable
              peer 10.0.0.2 reflect-client
             undo peer 10.0.0.3 enable
             #
             link-state-family unicast
              peer 10.0.0.3 enable
             #
             l2vpn-family evpn
              peer 10.0.0.3 enable
              peer 10.0.0.4 as-number 65002
              peer 10.0.0.4 enable
             #
             ipv4-family vpn-instance blue
              preference 33 34 35
              peer 10.0.0.3 as-number 65100
            #
            """);
    assertFalse(vc.getWarnings().getParseWarnings().toString(), vc.getUnrecognized());
    var c = vc.toVendorIndependentConfigurations().get(0);
    var peers = c.getDefaultVrf().getBgpProcess().getActiveNeighbors();
    assertEquals(1, peers.size());
    assertTrue(
        peers.get(Ip.parse("10.0.0.2")).getIpv4UnicastAddressFamily().getRouteReflectorClient());
    assertEquals(
        Long.valueOf(Ip.parse("10.0.0.1").asLong()),
        peers.get(Ip.parse("10.0.0.2")).getClusterId());
    assertTrue(
        peers
            .get(Ip.parse("10.0.0.2"))
            .getIpv4UnicastAddressFamily()
            .getAddressFamilyCapabilities()
            .getSendCommunity());
    var blue = c.getVrfs().get("blue").getBgpProcess();
    assertEquals(33, blue.getEbgpAdminCost());
    assertEquals(34, blue.getIbgpAdminCost());
    assertEquals(35, blue.getLocalAdminCost());
    assertEquals(1, blue.getActiveNeighbors().size());
    assertEquals(
        65100L,
        blue.getActiveNeighbors().get(Ip.parse("10.0.0.3")).getRemoteAsns().least().longValue());
  }

  @Test
  public void testUnknownAndSecretDiagnostics() {
    var vc = parse("sysname r2\ninterface GE1/0/0\n undo mystery SECRET\n bogus SECRET\n#\n");
    assertTrue(vc.getUnrecognized());
    assertEquals(2, vc.getWarnings().getParseWarnings().size());
    assertTrue(
        vc.getWarnings().getParseWarnings().stream()
            .noneMatch(w -> w.getText().contains("SECRET") || w.getComment().contains("SECRET")));
  }

  @Test
  public void testMalformedPeer() {
    var bad =
        parse(
            "sysname r2\n"
                + "bgp 65000\n"
                + " peer 192.0.2.1 as-number 65001\n"
                + " ipv4-family unicast\n"
                + "  peer 192.0.2.1 enable nonsense\n"
                + "#\n");
    assertTrue(bad.getUnrecognized());
  }

  @Test
  public void testInheritedBfd() {
    var vc =
        parse(
            """
            sysname r2
            isis 10
             is-level level-2
             network-entity 49.0001.0000.0000.0001.00
             bfd all-interfaces enable
             bfd all-interfaces min-tx-interval 20 min-rx-interval 20
            #
            interface GE1/0/0
             ip address 192.0.2.1 30
             isis enable 10
            #
            """);
    var c = vc.toVendorIndependentConfigurations().get(0);
    assertEquals(
        Integer.valueOf(20),
        c.getAllInterfaces().get("GE1/0/0").getIsis().getBfdLivenessDetectionMinimumInterval());
  }
}
