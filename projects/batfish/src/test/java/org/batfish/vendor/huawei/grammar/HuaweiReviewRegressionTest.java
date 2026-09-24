package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.batfish.datamodel.Bgpv4Route;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.bgp.community.ExtendedCommunity;
import org.batfish.datamodel.bgp.community.StandardCommunity;
import org.batfish.datamodel.routing_policy.Environment;
import org.batfish.datamodel.routing_policy.communities.CommunitySet;
import org.junit.Test;

public final class HuaweiReviewRegressionTest {
  private static void checkSource(String commands) {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            interface LoopBack0
             ip address 192.0.2.1 32
            #
            interface LoopBack1
             ip address 192.0.2.2 32
            #
            bgp 65000
             group G internal
             peer G connect-interface LoopBack0 192.0.2.1
             peer 198.51.100.1 group G
            """
                + commands);
    assertFalse(vc.getUnrecognized());
    var base = vc.getBgpProcesses().get(0).vrfs.get("default");
    var effective =
        org.batfish.vendor.huawei.representation.HuaweiBgpInheritance.ipv4Peers(base)
            .get("198.51.100.1");
    assertEquals("LoopBack1", effective.sourceInterface);
    assertNull(effective.sourceIp);
    var peer =
        vc.toVendorIndependentConfigurations()
            .get(0)
            .getDefaultVrf()
            .getBgpProcess()
            .getActiveNeighbors()
            .get(Ip.parse("198.51.100.1"));
    assertEquals(Ip.parse("192.0.2.2"), peer.getLocalIp());
  }

  @Test
  public void testMemberSourceOverridesGroupAtomically() {
    checkSource(" peer 198.51.100.1 connect-interface LoopBack1\n#\n");
  }

  @Test
  public void testAfSourceOverridesBaseAtomically() {
    checkSource(" ipv4-family unicast\n  peer 198.51.100.1 connect-interface LoopBack1\n#\n");
  }

  @Test
  public void testRepeatedSourceCommandClearsExplicitIp() {
    checkSource(
        " peer 198.51.100.1 connect-interface LoopBack0 192.0.2.1\n"
            + " peer 198.51.100.1 connect-interface LoopBack1\n"
            + "#\n");
  }

  @Test
  public void testUnsupportedIsisFamilyDoesNotLeakIpv6Imports() {
    var vc =
        HuaweiGrammarTest.parse(
            """
            sysname r2
            isis 10
             network-entity 49.0001.0000.0000.0001.00
             address-family ipv6 unicast
              import-route static
             #
             import-route bgp
            #
            """);
    assertTrue(vc.getUnrecognized());
    assertEquals(java.util.Set.of("bgp"), vc.getIsisProcesses().get(10).redistribution.keySet());
  }

  @Test
  public void testNativeIsisIpv6ImportDoesNotLeak() {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r2\n"
                + "isis 10\n"
                + " ipv6 enable topology ipv6\n"
                + " ipv6 import-route static route-policy V6\n"
                + " import-route bgp\n"
                + "#\n");
    assertFalse(vc.getUnrecognized());
    assertTrue(vc.getIsisProcesses().get(10).ipv6);
    assertEquals(java.util.Set.of("bgp"), vc.getIsisProcesses().get(10).redistribution.keySet());
    assertTrue(
        vc.getStructureManager()
            .getStructureReferences(
                org.batfish.vendor.huawei.representation.HuaweiStructureType.ROUTE_POLICY)
            .containsKey("V6"));
  }

  private static void checkMalformedList(boolean extended) {
    String kind = extended ? "extcommunity" : "community";
    String valid = extended ? "rt 65000:1" : "65000:1";
    String malformed = extended ? "rt not-an-extended-community" : "not-a-community";
    // A malformed deny preceding a valid permit must disable the whole named list,
    // not be discarded so the later permit starts accepting formerly denied input.
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r2\nip "
                + kind
                + "-filter basic C index 10 deny "
                + malformed
                + "\nip "
                + kind
                + "-filter basic C index 20 permit "
                + valid
                + "\nroute-policy P permit node 10\n if-match "
                + kind
                + "-filter C\n#\n");
    var c = vc.toVendorIndependentConfigurations().get(0);
    assertTrue(vc.getUnrecognized());
    assertEquals(1, vc.getWarnings().getParseWarnings().size());
    assertTrue(
        vc.getWarnings().getParseWarnings().stream()
            .noneMatch(w -> w.getText().contains("not-a") || w.getComment().contains("not-a")));
    var in =
        Bgpv4Route.testBuilder()
            .setNetwork(Prefix.parse("192.0.2.0/24"))
            .setOriginatorIp(Ip.parse("192.0.2.1"))
            .setProtocol(RoutingProtocol.BGP)
            .setCommunities(
                CommunitySet.of(
                    extended
                        ? ExtendedCommunity.target(65000, 1)
                        : StandardCommunity.parse("65000:1")))
            .build();
    assertFalse(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testMalformedStandardListIsDisabled() {
    checkMalformedList(false);
  }

  @Test
  public void testMalformedExtendedListIsDisabled() {
    checkMalformedList(true);
  }

  @Test
  public void testPlainIpv4BgpDoesNotWarn() {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r2\n"
                + "bgp 65000\n"
                + " peer 192.0.2.1 as-number 65001\n"
                + " ipv4-family unicast\n"
                + "  peer 192.0.2.1 enable\n"
                + "#\n");
    vc.toVendorIndependentConfigurations();
    assertTrue(vc.getWarnings().getRedFlagWarnings().isEmpty());
  }
}
