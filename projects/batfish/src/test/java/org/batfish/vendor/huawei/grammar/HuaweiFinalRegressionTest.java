package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class HuaweiFinalRegressionTest {
  @Test
  public void testPolicyMetricOverridesRedistributionModifier() {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r1\n"
                + "interface GE1/0/0\n"
                + " ip address 192.0.2.1 24\n"
                + " isis enable 10\n"
                + "#\n"
                + "isis 10\n"
                + " is-level level-2\n"
                + " network-entity 49.0001.0000.0000.0001.00\n"
                + " import-route static cost 50 route-policy P\n"
                + "#\n"
                + "bgp 65000\n"
                + " peer 192.0.2.2 as-number 65001\n"
                + " ipv4-family unicast\n"
                + "  import-route static route-policy P med 77\n"
                + "#\n"
                + "route-policy P permit node 10\n"
                + " apply cost 88\n"
                + "#\n");
    var c = vc.toVendorIndependentConfigurations().get(0);
    var in =
        org.batfish.datamodel.StaticRoute.builder()
            .setNetwork(org.batfish.datamodel.Prefix.parse("203.0.113.0/24"))
            .setNextHop(org.batfish.datamodel.route.nh.NextHopDiscard.instance())
            .setAdministrativeCost(60)
            .build();
    var bgpOut = org.batfish.datamodel.Bgpv4Route.testBuilder();
    var name =
        c.getDefaultVrf()
            .getBgpProcess()
            .getActiveNeighbors()
            .values()
            .iterator()
            .next()
            .getIpv4UnicastAddressFamily()
            .getExportPolicy();
    assertTrue(
        c.getRoutingPolicies()
            .get(name)
            .process(in, bgpOut, org.batfish.datamodel.routing_policy.Environment.Direction.OUT));
    assertEquals(88, bgpOut.getMetric());
    var isisOut =
        org.batfish.dataplane.protocols.IsisProtocolHelper.exportNonIsisRouteToIsis(
            new org.batfish.datamodel.AnnotatedRoute<>(in, "default"),
            c.getDefaultVrf().getIsisProcess(),
            false,
            c);
    assertEquals(88, isisOut.getMetric());
  }

  @Test
  public void testDualLevelIsisRedistributionIsConservative() {
    for (String level : new String[] {"level-1", "level-1-2"}) {
      var vc =
          HuaweiGrammarTest.parse(
              "sysname r1\n"
                  + "interface GE1/0/0\n"
                  + " ip address 192.0.2.1 24\n"
                  + " isis enable 10\n"
                  + "#\n"
                  + "isis 10\n"
                  + " is-level "
                  + level
                  + "\n"
                  + " network-entity 49.0001.0000.0000.0001.00\n"
                  + " import-route static cost 50\n"
                  + "#\n");
      var c = vc.toVendorIndependentConfigurations().get(0);
      assertTrue(
          vc.getWarnings().getRedFlagWarnings().stream()
              .anyMatch(w -> w.getText().contains("redistribution")));
      var in =
          org.batfish.datamodel.StaticRoute.builder()
              .setNetwork(org.batfish.datamodel.Prefix.parse("203.0.113.0/24"))
              .setNextHop(org.batfish.datamodel.route.nh.NextHopDiscard.instance())
              .setAdministrativeCost(60)
              .build();
      assertNull(
          org.batfish.dataplane.protocols.IsisProtocolHelper.exportNonIsisRouteToIsis(
              new org.batfish.datamodel.AnnotatedRoute<>(in, "default"),
              c.getDefaultVrf().getIsisProcess(),
              true,
              c));
      assertNotNull(c.getAllInterfaces().get("GE1/0/0").getIsis().getLevel1());
    }
  }

  @Test
  public void testAllVpnIsisWarns() {
    var vc =
        HuaweiGrammarTest.parse(
            "sysname r1\n"
                + "ip vpn-instance blue\n"
                + "#\n"
                + "isis 10 vpn-instance blue\n"
                + " network-entity 49.0001.0000.0000.0001.00\n"
                + "#\n");
    vc.toVendorIndependentConfigurations();
    assertTrue(
        vc.getWarnings().getRedFlagWarnings().stream()
            .anyMatch(w -> w.getText().startsWith("Huawei ISIS:")));
  }

  @Test
  public void testMalformedRedistributionTailOmitted() {
    for (String command :
        new String[] {
          "import-route static nonsense",
          "import-route static med",
          "import-route static med 77 junk",
          "import-route static med -1",
          "import-route static route-policy",
          "import-route static med 1 med 2"
        }) {
      var vc =
          HuaweiGrammarTest.parse(
              "sysname r1\nbgp 65000\n ipv4-family unicast\n  " + command + "\n#\n");
      assertTrue(command, vc.getUnrecognized());
      assertTrue(
          vc.getBgpProcesses()
              .get(0)
              .vrfs
              .get("default")
              .families
              .get("ipv4-family unicast")
              .redistribution
              .isEmpty());
    }
    for (String command :
        new String[] {
          "import-route bgp nonsense",
          "import-route bgp cost",
          "import-route bgp cost 50 junk",
          "import-route bgp cost -1",
          "import-route bgp cost-type nonsense"
        }) {
      var vc = HuaweiGrammarTest.parse("sysname r1\nisis 10\n " + command + "\n#\n");
      assertTrue(command, vc.getUnrecognized());
      assertTrue(vc.getIsisProcesses().get(10).redistribution.isEmpty());
    }
  }

  @Test
  public void testValidUnsupportedRedistributionOmittedAndWarned() {
    for (String command :
        new String[] {
          "import-route static route-filter X",
          "import-route direct exclude vlink",
          "import-route ospf 2"
        }) {
      var vc =
          HuaweiGrammarTest.parse(
              "sysname r1\nbgp 65000\n ipv4-family unicast\n  " + command + "\n#\n");
      assertFalse(command, vc.getUnrecognized());
      assertTrue(
          vc.getBgpProcesses()
              .get(0)
              .vrfs
              .get("default")
              .families
              .get("ipv4-family unicast")
              .redistribution
              .isEmpty());
      vc.toVendorIndependentConfigurations();
      assertTrue(
          vc.getWarnings().getRedFlagWarnings().stream()
              .anyMatch(w -> w.getText().contains("redistribution")));
    }
    for (String command :
        new String[] {
          "import-route bgp cost-type external",
          "import-route bgp inherit-cost",
          "import-route bgp level-1",
          "import-route bgp tag 50"
        }) {
      var vc = HuaweiGrammarTest.parse("sysname r1\nisis 10\n " + command + "\n#\n");
      assertFalse(command, vc.getUnrecognized());
      assertTrue(vc.getIsisProcesses().get(10).redistribution.isEmpty());
      vc.toVendorIndependentConfigurations();
      assertTrue(
          vc.getWarnings().getRedFlagWarnings().stream()
              .anyMatch(w -> w.getText().contains("redistribution")));
    }
  }
}
