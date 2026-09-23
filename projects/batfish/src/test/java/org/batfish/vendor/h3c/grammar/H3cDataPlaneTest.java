package org.batfish.vendor.h3c.grammar;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Map;
import java.util.Set;
import org.batfish.datamodel.AbstractRoute;
import org.batfish.datamodel.DataPlane;
import org.batfish.datamodel.Prefix;
import org.batfish.datamodel.RoutingProtocol;
import org.batfish.main.Batfish;
import org.batfish.main.BatfishTestUtils;
import org.batfish.main.TestrigText;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Two-node routing tests through the same ingestion and dataplane as client questions. */
public final class H3cDataPlaneTest {
  @Rule public TemporaryFolder folder = new TemporaryFolder();

  private static String node(int n, long asn, long remoteAs) {
    int other = 3 - n;
    return """
    #BATFISH_FORMAT: h3c_comware
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
     ip address 172.16.%d.1 32
    #
    isis 10
     is-level level-2
     network-entity 49.0001.0000.0000.000%d.00
     address-family ipv4 unicast
    #
    bgp %d
     ip vpn-instance blue
      peer 198.51.100.%d as-number %d
      address-family ipv4 unicast
       import-route direct
       import-route static
       peer 198.51.100.%d enable
       peer 198.51.100.%d advertise-community
       peer 198.51.100.%d route-policy EXPORT export
    #
    route-policy EXPORT permit node 10
     apply cost 77
     apply community 65000:77 additive
    #
    ip route-static vpn-instance blue 203.0.%d.0 24 NULL0
    ip route-static 198.51.100.0 30 vpn-instance blue
    return
    """
        .formatted(n, n, n, n, n, n, n, asn, other, remoteAs, other, other, other, n);
  }

  private DataPlane dataplane(boolean ibgp) throws Exception {
    long r2As = ibgp ? 65001 : 65002;
    Batfish batfish =
        BatfishTestUtils.getBatfishFromTestrigText(
            TestrigText.builder()
                .setConfigurationBytes(
                    Map.of(
                        "r1",
                        node(1, 65001, r2As).getBytes(UTF_8),
                        "r2",
                        node(2, r2As, 65001).getBytes(UTF_8)))
                .build(),
            folder);
    batfish.computeDataPlane(batfish.getSnapshot());
    return batfish.loadDataPlane(batfish.getSnapshot());
  }

  @Test
  public void testIsisAndEbgpVrfRoutes() throws Exception {
    DataPlane dp = dataplane(false);
    Set<AbstractRoute> global = dp.getRibs().get("r1", "default").getRoutes();
    assertTrue(
        global.stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("10.0.0.2/32"))
                        && r.getProtocol() == RoutingProtocol.ISIS_L2
                        && r.getAdministrativeCost() == 15));
    assertTrue(
        global.stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("198.51.100.0/30"))
                        && r.getNextHop()
                            .equals(org.batfish.datamodel.route.nh.NextHopVrf.of("blue"))));
    Set<AbstractRoute> blue = dp.getRibs().get("r1", "blue").getRoutes();
    AbstractRoute learnedStatic =
        blue.stream()
            .filter(r -> r.getNetwork().equals(Prefix.parse("203.0.2.0/24")))
            .findFirst()
            .orElseThrow();
    assertEquals(RoutingProtocol.BGP, learnedStatic.getProtocol());
    assertEquals(77, learnedStatic.getMetric());
    assertTrue(
        blue.stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("172.16.2.1/32"))
                        && r.getProtocol() == RoutingProtocol.BGP));
    assertTrue(
        blue.stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("203.0.1.0/24"))
                        && r.getAdministrativeCost() == 60));
    assertTrue(
        blue.stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("198.51.100.0/30"))
                        && r.getProtocol() == RoutingProtocol.CONNECTED));
  }

  @Test
  public void testIbgpVrfRoutes() throws Exception {
    assertTrue(
        dataplane(true).getRibs().get("r1", "blue").getRoutes().stream()
            .anyMatch(
                r ->
                    r.getNetwork().equals(Prefix.parse("203.0.2.0/24"))
                        && r.getProtocol() == RoutingProtocol.IBGP));
  }
}
