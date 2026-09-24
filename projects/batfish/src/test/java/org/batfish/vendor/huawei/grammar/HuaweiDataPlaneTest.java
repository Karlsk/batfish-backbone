package org.batfish.vendor.huawei.grammar;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Map;
import org.batfish.datamodel.AbstractRoute;
import org.batfish.datamodel.Bgpv4Route;
import org.batfish.datamodel.DataPlane;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.datamodel.bgp.community.StandardCommunity;
import org.batfish.datamodel.isis.IsisTopology;
import org.batfish.datamodel.route.nh.NextHopDiscard;
import org.batfish.datamodel.route.nh.NextHopVrf;
import org.batfish.main.Batfish;
import org.batfish.main.BatfishTestUtils;
import org.batfish.main.TestrigText;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/**
 * Synthetic configurations exercise ingestion, protocol convergence, and the resulting main RIB.
 */
public final class HuaweiDataPlaneTest {
  @Rule public TemporaryFolder folder = new TemporaryFolder();

  private Batfish compute(Map<String, String> configs) throws Exception {
    var bytes = new java.util.HashMap<String, byte[]>();
    configs.forEach((name, text) -> bytes.put(name, text.getBytes(UTF_8)));
    Batfish batfish =
        BatfishTestUtils.getBatfishFromTestrigText(
            TestrigText.builder().setConfigurationBytes(bytes).build(), folder);
    batfish.computeDataPlane(batfish.getSnapshot());
    return batfish;
  }

  private static AbstractRoute route(DataPlane dp, String node, String vrf, String prefix) {
    return dp.getRibs().get(node, vrf).getRoutes().stream()
        .filter(r -> r.getNetwork().equals(Prefix.parse(prefix)))
        .findFirst()
        .orElseThrow(() -> new AssertionError(node + "/" + vrf + " missing " + prefix));
  }

  private static void absent(DataPlane dp, String node, String vrf, String prefix) {
    assertTrue(
        node + "/" + vrf + " unexpectedly learned " + prefix,
        dp.getRibs().get(node, vrf).getRoutes().stream()
            .noneMatch(r -> r.getNetwork().equals(Prefix.parse(prefix))));
  }

  private static String dualNode(int n, long asn, long remoteAs, boolean h3c, boolean preference) {
    int other = 3 - n;
    String vpnFamily =
        h3c
            ? "ip vpn-instance blue\n  address-family ipv4 unicast"
            : "ipv4-family vpn-instance blue";
    return """
    #BATFISH_FORMAT: %s
    sysname r%d
    router id 10.0.0.%d
    ip vpn-instance blue
    #
    interface LoopBack0
     ip address 10.0.0.%d 32
     isis enable 10
    #
    interface GigabitEthernet1/0/1
     ip address 192.0.2.%d 30
     isis enable 10
     isis circuit-type p2p
    #
    interface GigabitEthernet1/0/2
     ip binding vpn-instance blue
     ip address 198.51.100.%d 30
    #
    interface LoopBack1
     ip binding vpn-instance blue
     ip address 198.51.100.%d 32
    #
    isis 10
     is-level level-2
     network-entity 49.0001.0000.0000.000%d.00
     %s
    #
    bgp %d
     %s
      peer 198.51.100.%d as-number %d
      import-route direct
      import-route static
      peer 198.51.100.%d enable
      peer 198.51.100.%d advertise-community
      peer 198.51.100.%d route-policy EXPORT export
      %s
    #
    route-policy EXPORT permit node 10
     apply cost 77
     apply community 65000:77 additive
    #
    ip route-static vpn-instance blue 203.0.113.%d 26 NULL0
    ip route-static vpn-instance blue 203.0.113.128 26 NULL0 preference %d
    ip route-static 198.51.100.0 30 vpn-instance blue
    return
    """
        .formatted(
            h3c ? "h3c_comware" : "huawei_vrp",
            n,
            n,
            n,
            n,
            n,
            16 + n,
            n,
            h3c ? "address-family ipv4 unicast" : "",
            asn,
            vpnFamily,
            other,
            remoteAs,
            other,
            other,
            other,
            preference ? "preference 33 2 255" : "",
            (n - 1) * 64,
            n == 1 ? 75 : 60)
        .replaceAll("(?m)^ +$", "");
  }

  private void checkDual(boolean ibgp, boolean mixed, boolean preference) throws Exception {
    long remoteAs = ibgp ? 65001 : 65002;
    Batfish batfish =
        compute(
            Map.of(
                "r1", dualNode(1, 65001, remoteAs, false, preference),
                "r2", dualNode(2, remoteAs, 65001, mixed, false)));
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertEquals(
        2,
        batfish
            .getTopologyProvider()
            .getBgpTopology(batfish.getSnapshot())
            .getGraph()
            .edges()
            .size());
    assertEquals(
        2,
        IsisTopology.initIsisTopology(
                batfish.loadConfigurations(batfish.getSnapshot()),
                batfish.getTopologyProvider().getLayer3Topology(batfish.getSnapshot()))
            .getNetwork()
            .edges()
            .size());
    for (int n = 1; n <= 2; n++) {
      String node = "r" + n;
      AbstractRoute isis = route(dp, node, "default", "10.0.0." + (3 - n) + "/32");
      assertEquals(RoutingProtocol.ISIS_L2, isis.getProtocol());
      assertEquals(15, isis.getAdministrativeCost());
      AbstractRoute nextTable = route(dp, node, "default", "198.51.100.0/30");
      assertEquals(NextHopVrf.of("blue"), nextTable.getNextHop());
      assertEquals(60, nextTable.getAdministrativeCost());
      assertEquals(
          RoutingProtocol.CONNECTED, route(dp, node, "blue", "198.51.100.0/30").getProtocol());
      AbstractRoute localStatic = route(dp, node, "blue", "203.0.113." + ((n - 1) * 64) + "/26");
      assertEquals(NextHopDiscard.instance(), localStatic.getNextHop());
      assertEquals(60, localStatic.getAdministrativeCost());
      Bgpv4Route learned =
          (Bgpv4Route) route(dp, node, "blue", "203.0.113." + ((2 - n) * 64) + "/26");
      assertEquals(ibgp ? RoutingProtocol.IBGP : RoutingProtocol.BGP, learned.getProtocol());
      assertEquals(preference && n == 1 ? (ibgp ? 2 : 33) : 255, learned.getAdministrativeCost());
      assertEquals(77, learned.getMetric());
      assertTrue(
          learned.getCommunities().getCommunities().contains(StandardCommunity.of(65000, 77)));
      assertEquals(
          ibgp ? RoutingProtocol.IBGP : RoutingProtocol.BGP,
          route(dp, node, "blue", "198.51.100." + (19 - n) + "/32").getProtocol());
      absent(dp, node, "default", "203.0.113." + ((2 - n) * 64) + "/26");
    }
    // A competing local static route proves preference changes actually affect route selection.
    AbstractRoute competing = route(dp, "r1", "blue", "203.0.113.128/26");
    assertEquals(
        preference ? (ibgp ? RoutingProtocol.IBGP : RoutingProtocol.BGP) : RoutingProtocol.STATIC,
        competing.getProtocol());
    assertEquals(preference ? (ibgp ? 2 : 33) : 75, competing.getAdministrativeCost());
  }

  @Test
  public void testHuaweiEbgpDefaultPreference() throws Exception {
    checkDual(false, false, false);
  }

  @Test
  public void testHuaweiIbgpExplicitPreference() throws Exception {
    checkDual(true, false, true);
  }

  @Test
  public void testMixedEbgpExplicitPreference() throws Exception {
    checkDual(false, true, true);
  }

  @Test
  public void testMixedIbgpDefaultPreference() throws Exception {
    checkDual(true, true, false);
  }

  private static String rrNode(int n, String peers) {
    return """
    #BATFISH_FORMAT: huawei_vrp
    sysname r%d
    interface GigabitEthernet1/0/1
     ip address 192.0.2.%d 24
    #
    bgp 65000
     router-id 10.0.0.%d
    %s
    #
    """
        .formatted(n, n, n, peers);
  }

  @Test
  public void testFinalPhysicalRouterIdFallbackConverges() throws Exception {
    var configs = new java.util.HashMap<String, String>();
    for (int n = 1; n <= 2; n++) {
      configs.put(
          "r" + n,
          rrNode(
                      n,
                      " peer 192.0.2."
                          + (3 - n)
                          + " as-number 65000\n ipv4-family unicast\n  import-route static\n")
                  .replace(" router-id 10.0.0." + n + "\n", "")
              + "ip route-static 203.0.113."
              + n
              + " 32 NULL0\n");
    }
    var batfish = compute(configs);
    var dp = batfish.loadDataPlane(batfish.getSnapshot());
    for (int n = 1; n <= 2; n++) {
      assertEquals(
          RoutingProtocol.IBGP,
          route(dp, "r" + n, "default", "203.0.113." + (3 - n) + "/32").getProtocol());
      assertEquals(
          org.batfish.datamodel.Ip.parse("192.0.2." + n),
          batfish
              .loadConfigurations(batfish.getSnapshot())
              .get("r" + n)
              .getDefaultVrf()
              .getBgpProcess()
              .getRouterId());
    }
  }

  @Test
  public void testFinalBgpDefaultImportAndExplicitNetwork() throws Exception {
    for (String command :
        new String[] {
          "",
          "  network 0.0.0.0 0\n",
          "  default-route imported\n",
          "  default-route imported\n  undo default-route imported\n"
        }) {
      var batfish =
          compute(
              Map.of(
                  "r1",
                  rrNode(
                          1,
                          " peer 192.0.2.2 as-number 65000\n"
                              + " ipv4-family unicast\n"
                              + "  import-route static\n"
                              + command)
                      + "ip route-static 0.0.0.0 0 NULL0\nip route-static 203.0.113.1 32 NULL0\n",
                  "r2",
                  rrNode(2, " peer 192.0.2.1 as-number 65000\n ipv4-family unicast\n")));
      var dp = batfish.loadDataPlane(batfish.getSnapshot());
      assertEquals(
          RoutingProtocol.IBGP, route(dp, "r2", "default", "203.0.113.1/32").getProtocol());
      if (command.isEmpty() || command.contains("undo")) {
        absent(dp, "r2", "default", "0.0.0.0/0");
      } else {
        assertEquals(RoutingProtocol.IBGP, route(dp, "r2", "default", "0.0.0.0/0").getProtocol());
      }
    }
  }

  @Test
  public void testFinalBgpRedistributionMedConverges() throws Exception {
    var batfish =
        compute(
            Map.of(
                "r1",
                rrNode(
                        1,
                        " peer 192.0.2.2 as-number 65000\n"
                            + " ipv4-family unicast\n"
                            + "  import-route static med 77\n")
                    + "ip route-static 203.0.113.1 32 NULL0\n",
                "r2",
                rrNode(2, " peer 192.0.2.1 as-number 65000\n ipv4-family unicast\n")));
    assertEquals(
        77,
        route(batfish.loadDataPlane(batfish.getSnapshot()), "r2", "default", "203.0.113.1/32")
            .getMetric());
  }

  private Batfish rr(String afOverride, boolean reflect) throws Exception {
    String reflector =
        rrNode(
                1,
                """
                 group CLIENTS internal
                 peer 192.0.2.2 group CLIENTS
                 peer 192.0.2.3 group CLIENTS
                 ipv4-family unicast
                  peer CLIENTS enable
                  peer CLIENTS advertise-community
                  peer CLIENTS route-policy IN import
                  peer CLIENTS route-policy OUT export
                %s
                %s
                """
                    .formatted(reflect ? "  peer CLIENTS reflect-client" : "", afOverride))
            + """
            ip ip-prefix DENY-IN index 10 permit 203.0.113.128 26
            ip ip-prefix DENY-OUT index 10 permit 203.0.113.64 26
            route-policy IN deny node 10
             if-match ip-prefix DENY-IN
            #
            route-policy IN permit node 20
            #
            route-policy OUT deny node 10
             if-match ip-prefix DENY-OUT
            #
            route-policy OUT permit node 20
             apply cost 77
             apply community 65000:77 additive
            #
            """;
    String client =
        """
         peer 192.0.2.1 as-number 65000
         ipv4-family unicast
          peer 192.0.2.1 enable
          peer 192.0.2.1 advertise-community
        """;
    String origin =
        rrNode(2, client + "  import-route static\n  network 203.0.113.192 26\n")
            + """
            interface LoopBack0
             ip address 203.0.113.193 26
            #
            ip route-static 203.0.113.0 26 NULL0
            ip route-static 203.0.113.64 26 NULL0
            ip route-static 203.0.113.128 26 NULL0
            """;
    return compute(Map.of("r1", reflector, "r2", origin, "r3", rrNode(3, client)));
  }

  @Test
  public void testGroupRouteReflectionPoliciesAndNetworkOrigination() throws Exception {
    Batfish batfish = rr("", true);
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    var graph = batfish.getTopologyProvider().getBgpTopology(batfish.getSnapshot()).getGraph();
    assertEquals(4, graph.edges().size());
    assertTrue(
        graph.edges().stream()
            .allMatch(
                e -> e.nodeU().getHostname().equals("r1") || e.nodeV().getHostname().equals("r1")));
    Bgpv4Route reflected = (Bgpv4Route) route(dp, "r3", "default", "203.0.113.0/26");
    assertEquals(RoutingProtocol.IBGP, reflected.getProtocol());
    assertEquals(255, reflected.getAdministrativeCost());
    assertEquals(77, reflected.getMetric());
    assertTrue(
        reflected.getCommunities().getCommunities().contains(StandardCommunity.of(65000, 77)));
    assertEquals(
        RoutingProtocol.IBGP, route(dp, "r3", "default", "203.0.113.192/26").getProtocol());
    assertEquals(RoutingProtocol.IBGP, route(dp, "r1", "default", "203.0.113.64/26").getProtocol());
    absent(dp, "r3", "default", "203.0.113.64/26");
    absent(dp, "r1", "default", "203.0.113.128/26");
    absent(dp, "r3", "default", "203.0.113.128/26");
  }

  @Test
  public void testIbgpDoesNotTransitWithoutReflection() throws Exception {
    Batfish batfish = rr("", false);
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertEquals(RoutingProtocol.IBGP, route(dp, "r1", "default", "203.0.113.0/26").getProtocol());
    absent(dp, "r3", "default", "203.0.113.0/26");
    absent(dp, "r3", "default", "203.0.113.192/26");
  }

  private void checkDisabled(String afOverride) throws Exception {
    Batfish batfish = rr(afOverride, true);
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertEquals(RoutingProtocol.IBGP, route(dp, "r1", "default", "203.0.113.0/26").getProtocol());
    absent(dp, "r3", "default", "203.0.113.0/26");
    assertFalse(
        batfish
            .getTopologyProvider()
            .getBgpTopology(batfish.getSnapshot())
            .getGraph()
            .edges()
            .stream()
            .anyMatch(
                e -> e.nodeU().getHostname().equals("r3") || e.nodeV().getHostname().equals("r3")));
  }

  @Test
  public void testAfMemberEnableOverridesGroupDisable() throws Exception {
    Batfish batfish = rr("  undo peer CLIENTS enable\n  peer 192.0.2.2 enable", true);
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertEquals(RoutingProtocol.IBGP, route(dp, "r1", "default", "203.0.113.0/26").getProtocol());
    absent(dp, "r3", "default", "203.0.113.0/26");
    assertEquals(
        2,
        batfish
            .getTopologyProvider()
            .getBgpTopology(batfish.getSnapshot())
            .getGraph()
            .edges()
            .size());
  }

  @Test
  public void testAfMemberDisableOverridesGroupEnable() throws Exception {
    checkDisabled("  undo peer 192.0.2.3 enable");
  }

  private void checkIsisRedistribution(boolean redistribute, Long cost) throws Exception {
    String border =
        rrNode(
                1,
                " peer 192.0.2.2 as-number 65001\n"
                    + " ipv4-family unicast\n  peer 192.0.2.2 enable\n")
            + """
            interface GigabitEthernet1/0/2
             ip address 198.51.100.1 30
             isis enable 10
             isis circuit-type p2p
            #
            isis 10
             is-level level-2
             network-entity 49.0001.0000.0000.0001.00
            %s
             import-route static
            #
            ip route-static 0.0.0.0 0 NULL0
            """
                .formatted(
                    redistribute
                        ? " import-route bgp" + (cost == null ? "" : " cost " + cost)
                        : "");
    String origin =
        rrNode(
                    2,
                    " peer 192.0.2.1 as-number 65000\n"
                        + " ipv4-family unicast\n  peer 192.0.2.1 enable\n  import-route static\n")
                .replace("bgp 65000", "bgp 65001")
            + "ip route-static 203.0.113.0 26 NULL0\n";
    String receiver =
        """
        #BATFISH_FORMAT: huawei_vrp
        sysname r3
        interface GigabitEthernet1/0/1
         ip address 198.51.100.2 30
         isis enable 10
         isis circuit-type p2p
        #
        isis 10
         is-level level-2
         network-entity 49.0001.0000.0000.0003.00
        #
        """;
    Batfish batfish = compute(Map.of("r1", border, "r2", origin, "r3", receiver));
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertEquals(RoutingProtocol.BGP, route(dp, "r1", "default", "203.0.113.0/26").getProtocol());
    if (redistribute) {
      AbstractRoute learned = route(dp, "r3", "default", "203.0.113.0/26");
      assertEquals(RoutingProtocol.ISIS_EL2, learned.getProtocol());
      assertEquals(15, learned.getAdministrativeCost());
      if (cost != null) {
        assertEquals(cost.longValue() + 10, learned.getMetric());
      }
    } else {
      absent(dp, "r3", "default", "203.0.113.0/26");
    }
    absent(dp, "r3", "default", "0.0.0.0/0");
  }

  @Test
  public void testIsisRedistributesLearnedBgpRoute() throws Exception {
    checkIsisRedistribution(true, null);
  }

  @Test
  public void testIsisDoesNotRedistributeBgpWithoutImport() throws Exception {
    checkIsisRedistribution(false, null);
  }

  @Test
  public void testFinalIsisRedistributionCostConverges() throws Exception {
    checkIsisRedistribution(true, 50L);
  }

  @Test
  public void testFinalNativeIsisL1AndDualStillConverge() throws Exception {
    for (String level : new String[] {"level-1", "level-1-2"}) {
      var configs = new java.util.HashMap<String, String>();
      for (int n = 1; n <= 2; n++) {
        configs.put(
            "r" + n,
            "#BATFISH_FORMAT: huawei_vrp\nsysname r"
                + n
                + "\ninterface GE1/0/0\n ip address 192.0.2."
                + n
                + " 30\n"
                + " isis enable 10\n"
                + " isis circuit-type p2p\n"
                + "#\n"
                + "interface LoopBack0\n"
                + " ip address 10.0.0."
                + n
                + " 32\n isis enable 10\n#\nisis 10\n is-level "
                + level
                + "\n network-entity 49.0001.0000.0000.000"
                + n
                + ".00\n import-route static cost 50\n#\nip route-static 203.0.113."
                + n
                + " 32 NULL0\n");
      }
      var batfish = compute(configs);
      var dp = batfish.loadDataPlane(batfish.getSnapshot());
      for (int n = 1; n <= 2; n++) {
        assertEquals(
            RoutingProtocol.ISIS_L1,
            route(dp, "r" + n, "default", "10.0.0." + (3 - n) + "/32").getProtocol());
        absent(dp, "r" + n, "default", "203.0.113." + (3 - n) + "/32");
      }
    }
  }

  private static String evpnNode(int n) {
    return rrNode(
            n,
            " l2vpn-family evpn\n"
                + "  peer 192.0.2."
                + (3 - n)
                + " as-number 65000\n"
                + "  peer 192.0.2."
                + (3 - n)
                + " enable\n")
        + """
        ip vpn-instance blue
         ipv4-family
          route-distinguisher 65000:%d
          vpn-target 65000:10 both evpn
        #
        evpn vpn-instance E bd-mode
         route-distinguisher 65000:%d
         vpn-target 65000:20 both
         segment-routing ipv6 locator L
        #
        bridge-domain 10
         evpn binding vpn-instance E
        #
        evpl instance 1
         evpn binding vpn-instance E
         local-service-id 100 remote-service-id 200
        #
        segment-routing ipv6
         locator L ipv6-prefix 2001:db8:%d:: 64 static 32
          opcode ::1 end-dt4 vpn-instance blue
          opcode ::2 end-dt2u bridge-domain 10
        #
        ip route-static vpn-instance blue 203.0.113.%d 26 NULL0
        """
            .formatted(n, n + 10, n, (n - 1) * 64);
  }

  @Test
  public void testRetainedEvpnDoesNotFabricateSessionsVnisOrVrfLeaks() throws Exception {
    Batfish batfish = compute(Map.of("r1", evpnNode(1), "r2", evpnNode(2)));
    DataPlane dp = batfish.loadDataPlane(batfish.getSnapshot());
    assertTrue(
        batfish
            .getTopologyProvider()
            .getBgpTopology(batfish.getSnapshot())
            .getGraph()
            .edges()
            .isEmpty());
    assertTrue(dp.getLayer2Vnis().values().stream().allMatch(java.util.Set::isEmpty));
    assertTrue(dp.getLayer3Vnis().values().stream().allMatch(java.util.Set::isEmpty));
    assertTrue(dp.getEvpnRoutes().values().stream().allMatch(java.util.Set::isEmpty));
    for (int n = 1; n <= 2; n++) {
      String local = "203.0.113." + ((n - 1) * 64) + "/26";
      assertEquals(NextHopDiscard.instance(), route(dp, "r" + n, "blue", local).getNextHop());
      absent(dp, "r" + n, "default", local);
      absent(dp, "r" + n, "blue", "203.0.113." + ((2 - n) * 64) + "/26");
    }
  }
}
