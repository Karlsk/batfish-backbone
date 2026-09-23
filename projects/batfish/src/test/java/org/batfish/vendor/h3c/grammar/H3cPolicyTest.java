package org.batfish.vendor.h3c.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.batfish.datamodel.Bgpv4Route;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.bgp.community.StandardCommunity;
import org.batfish.datamodel.routing_policy.Environment;
import org.batfish.datamodel.routing_policy.communities.CommunitySet;
import org.junit.Test;

public final class H3cPolicyTest {
  private static final String CONFIG =
      """
      sysname r1
      route-policy P permit node 20
       if-match ip address prefix-list A B
       if-match community name C
       apply community 65000:200 additive
       apply cost 123
       apply local-preference 321
       apply ip-address next-hop 192.0.2.1
      #
      route-policy P deny node 10
       if-match ip address prefix-list DENY
      #
      route-policy UNDEFINED permit node 10
       if-match ip address prefix-list absent
      #
      route-policy RD permit node 10
       if-match rd-list 1
      #
      route-policy COLOR permit node 10
       apply extcommunity color 00:1000
      #
      ip prefix-list A index 10 permit 10.0.0.0 8 greater-equal 16 less-equal 24
      ip prefix-list B index 10 permit 192.168.0.0 16
      ip prefix-list DENY index 10 permit 10.1.0.0 16
      ip community-list basic C permit 65000:100
      ip rd-list 1 index 10 permit 65000:1
      """;

  private static Bgpv4Route route(String prefix, boolean community) {
    return Bgpv4Route.testBuilder()
        .setNetwork(Prefix.parse(prefix))
        .setOriginatorIp(Ip.parse("1.1.1.1"))
        .setProtocol(RoutingProtocol.BGP)
        .setCommunities(
            community
                ? CommunitySet.of(StandardCommunity.parse("65000:100"))
                : CommunitySet.empty())
        .build();
  }

  @Test
  public void testWholeMatchCannotBecomeUndefinedListMatch() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                route-policy P permit node 10
                 if-match community name C whole-match
                #
                ip community-list basic C permit 65000:100
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    Bgpv4Route in = route("192.0.2.0/24", false);
    assertFalse(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testExtcommunityIndicesAreOrdered() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                route-policy P permit node 10
                 if-match extcommunity 100
                #
                ip extcommunity-list 100 index 20 permit rt 65000:1
                ip extcommunity-list 100 index 10 deny rt 65000:1
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    Bgpv4Route in =
        route("192.0.2.0/24", false).toBuilder()
            .setCommunities(
                CommunitySet.of(
                    org.batfish.datamodel.bgp.community.ExtendedCommunity.target(65000, 1)))
            .build();
    assertFalse(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testSooIsNotRouteTarget() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                route-policy P permit node 10
                 if-match extcommunity 1
                #
                ip extcommunity-list 1 permit soo 65000:1
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    Bgpv4Route in =
        route("192.0.2.0/24", false).toBuilder()
            .setCommunities(
                CommunitySet.of(
                    org.batfish.datamodel.bgp.community.ExtendedCommunity.target(65000, 1)))
            .build();
    assertFalse(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
    in =
        in.toBuilder()
            .setCommunities(
                CommunitySet.of(
                    org.batfish.datamodel.bgp.community.ExtendedCommunity.parse("origin:65000:1")))
            .build();
    assertTrue(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testAutomaticPrefixIndexDoesNotOverwriteExplicitEntry() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                ip prefix-list P index 10 deny 192.0.2.0 24
                ip prefix-list P permit 198.51.100.0 24
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    assertEquals(2, c.getRouteFilterLists().get("P").getLines().size());
    assertFalse(c.getRouteFilterLists().get("P").permits(Prefix.parse("192.0.2.0/24")));
    assertTrue(c.getRouteFilterLists().get("P").permits(Prefix.parse("198.51.100.0/24")));
  }

  @Test
  public void testNumberedAdvancedCommunityListIsConservative() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                ip community-list 100 permit ^10
                route-policy P permit node 10
                 if-match community 100
                #
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    Bgpv4Route in = route("192.0.2.0/24", false);
    assertFalse(
        c.getRoutingPolicies().get("P").process(in, in.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testOrderedNodesAndOrAndActions() throws Exception {
    Configuration c = H3cGrammarTest.parse(CONFIG).toVendorIndependentConfigurations().get(0);
    var policy = c.getRoutingPolicies().get("P");
    Bgpv4Route input = route("10.2.0.0/16", true);
    Bgpv4Route.Builder output = input.toBuilder();
    assertTrue(policy.process(input, output, Environment.Direction.OUT));
    assertEquals(123, output.getMetric());
    assertEquals(321, output.getLocalPreference());
    assertEquals(Ip.parse("192.0.2.1"), output.getNextHopIp());
    assertTrue(
        output
            .build()
            .getCommunities()
            .getCommunities()
            .contains(StandardCommunity.parse("65000:200")));
    for (String prefix : new String[] {"10.1.0.0/16", "10.2.0.0/25", "203.0.113.0/24"}) {
      Bgpv4Route denied = route(prefix, true);
      assertFalse(policy.process(denied, denied.toBuilder(), Environment.Direction.OUT));
    }
    Bgpv4Route noCommunity = route("10.2.0.0/16", false);
    assertFalse(policy.process(noCommunity, noCommunity.toBuilder(), Environment.Direction.OUT));
    Bgpv4Route secondPrefix = route("192.168.0.0/16", true);
    assertTrue(policy.process(secondPrefix, secondPrefix.toBuilder(), Environment.Direction.OUT));
  }

  @Test
  public void testUndefinedListAndUnconvertibleMatchAndColor() throws Exception {
    Configuration c = H3cGrammarTest.parse(CONFIG).toVendorIndependentConfigurations().get(0);
    Bgpv4Route input = route("203.0.113.0/24", false);
    assertTrue(
        c.getRoutingPolicies()
            .get("UNDEFINED")
            .process(input, input.toBuilder(), Environment.Direction.OUT));
    assertFalse(
        c.getRoutingPolicies()
            .get("RD")
            .process(input, input.toBuilder(), Environment.Direction.OUT));
    Bgpv4Route.Builder output = input.toBuilder();
    assertTrue(
        c.getRoutingPolicies().get("COLOR").process(input, output, Environment.Direction.OUT));
    assertTrue(
        output
            .build()
            .getCommunities()
            .getCommunities()
            .contains(
                org.batfish.datamodel.bgp.community.ExtendedCommunity.opaque(true, 11, 1000)));
  }

  @Test
  public void testBgpNetworkOriginAndRedistributionMetric() throws Exception {
    Configuration c =
        H3cGrammarTest.parse(
                """
                sysname r1
                router id 10.0.0.1
                bgp 65000
                 peer 192.0.2.2 as-number 65001
                 address-family ipv4 unicast
                  network 203.0.113.0 24
                  peer 192.0.2.2 enable
                #
                route-policy METRIC permit node 10
                 apply cost 77
                #
                isis 1
                 network-entity 49.0001.0000.0000.0001.00
                 address-family ipv4 unicast
                  import-route bgp route-policy METRIC
                #
                """)
            .toVendorIndependentConfigurations()
            .get(0);
    var in =
        org.batfish.datamodel.StaticRoute.builder()
            .setNetwork(Prefix.parse("203.0.113.0/24"))
            .setAdministrativeCost(60)
            .setNextHop(org.batfish.datamodel.route.nh.NextHopDiscard.instance())
            .build();
    Bgpv4Route.Builder out = Bgpv4Route.testBuilder();
    String export =
        c.getDefaultVrf()
            .getBgpProcess()
            .getActiveNeighbors()
            .get(Ip.parse("192.0.2.2"))
            .getIpv4UnicastAddressFamily()
            .getExportPolicy();
    assertTrue(c.getRoutingPolicies().get(export).process(in, out, Environment.Direction.OUT));
    assertEquals(org.batfish.datamodel.OriginType.IGP, out.getOriginType());
    var isisOut = org.batfish.datamodel.IsisRoute.builder();
    assertTrue(
        c.getRoutingPolicies()
            .get(c.getDefaultVrf().getIsisProcess().getExportPolicy())
            .process(route("203.0.113.0/24", false), isisOut, Environment.Direction.OUT));
    assertEquals(77, isisOut.getMetric());
  }
}
