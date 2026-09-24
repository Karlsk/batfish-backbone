package org.batfish.vendor.huawei.grammar;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.batfish.datamodel.ConcreteInterfaceAddress;
import org.batfish.datamodel.InterfaceType;
import org.batfish.datamodel.answers.ParseStatus;
import org.batfish.datamodel.route.nh.NextHopDiscard;
import org.batfish.main.BatfishTestUtils;
import org.batfish.main.TestrigText;
import org.batfish.vendor.huawei.representation.HuaweiConfiguration;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public final class HuaweiProductionTest {
  @Rule public TemporaryFolder folder = new TemporaryFolder();

  @Test
  public void testWhitespaceOnlyLinesParseThroughProduction() throws Exception {
    String text =
        "!Software Version V800R023C00SPC500\n"
            + "sysname r1\n"
            + "isis 10\n"
            + " is-level level-2\n"
            + " network-entity 49.0001.0000.0000.0001.00\n"
            + " \n"
            + "\t\n"
            + " \t \n"
            + "#\n";
    var batfish =
        BatfishTestUtils.getBatfishFromTestrigText(
            TestrigText.builder()
                .setConfigurationBytes(Map.of("r1", text.getBytes(StandardCharsets.UTF_8)))
                .build(),
            folder);
    assertEquals(
        ParseStatus.PASSED,
        batfish
            .loadParseVendorConfigurationAnswerElement(batfish.getSnapshot())
            .getParseStatus()
            .get("configs/r1"));
    var vc =
        (HuaweiConfiguration) batfish.loadVendorConfigurations(batfish.getSnapshot()).get("r1");
    assertEquals("49.0001.0000.0000.0001.00", vc.getIsisProcesses().get(10).net);
    assertEquals("level-2", vc.getIsisProcesses().get(10).level);
    assertNotNull(batfish.loadConfigurations(batfish.getSnapshot()).get("r1"));
  }

  @Test
  public void testEncodingInterfacesStaticAndIsis() throws Exception {
    String text =
        """
        !Software Version V800R023C00SPC500
        sysname r2
        ip vpn-instance blue
         ipv4-family
          route-distinguisher 65000:1
        #
        interface Eth-Trunk1
         description 南京机房核心路由器连接测试网络设备接口配置
         mtu 9000
         ip address 192.0.2.1 30
         isis enable 10
         isis circuit-type p2p
         isis cost 17 level-2
        #
        interface GE1/0/0
         eth-trunk 1
        #
        interface Eth-Trunk1.100
         vlan-type dot1q 100
         ip binding vpn-instance blue
         ip address 198.51.100.1 24
        #
        interface Vlanif200
         shutdown
         ip address 203.0.113.1 24
        #
        interface LoopBack0
         ip address 10.0.0.1 32
         isis enable 10
        #
        isis 20
         network-entity 49.0001.0000.0000.0020.00
        #
        isis 10
         network-entity 49.0001.0000.0000.0010.00
         is-level level-2
        #
        ip route-static 203.0.114.0 24 NULL0 preference 120 tag 7 description test
        ip route-static vpn-instance blue 0.0.0.0 0 198.51.100.2
        """;
    for (Charset encoding : java.util.List.of(StandardCharsets.UTF_8, Charset.forName("GB18030"))) {
      var batfish =
          BatfishTestUtils.getBatfishFromTestrigText(
              TestrigText.builder()
                  .setConfigurationBytes(
                      Map.of("r2", text.replace("\n", "\r\r\n").getBytes(encoding)))
                  .build(),
              folder);
      var vc =
          (HuaweiConfiguration) batfish.loadVendorConfigurations(batfish.getSnapshot()).get("r2");
      assertEquals("南京机房核心路由器连接测试网络设备接口配置", vc.getInterfaces().get("Eth-Trunk1").description);
      assertEquals(
          ParseStatus.PASSED,
          batfish
              .loadParseVendorConfigurationAnswerElement(batfish.getSnapshot())
              .getParseStatus()
              .get("configs/r2"));
      var c = batfish.loadConfigurations(batfish.getSnapshot()).get("r2");
      var trunk = c.getAllInterfaces().get("Eth-Trunk1");
      assertEquals(InterfaceType.AGGREGATED, trunk.getInterfaceType());
      assertEquals(9000, trunk.getMtu());
      assertTrue(trunk.getChannelGroupMembers().contains("GE1/0/0"));
      assertEquals(
          ConcreteInterfaceAddress.parse("198.51.100.1/24"),
          c.getAllInterfaces().get("Eth-Trunk1.100").getConcreteAddress());
      assertEquals("blue", c.getAllInterfaces().get("Eth-Trunk1.100").getVrfName());
      assertEquals(
          Integer.valueOf(100), c.getAllInterfaces().get("Eth-Trunk1.100").getEncapsulationVlan());
      assertNotNull(c.getAllInterfaces().get("Vlanif200").getInactiveReason());
      assertEquals(
          vc.getIsisProcesses().get(10).net,
          c.getDefaultVrf().getIsisProcess().getNetAddress().toString());
      assertTrue(trunk.getIsis().getPointToPoint());
      assertEquals(Long.valueOf(17), trunk.getIsis().getLevel2().getCost());
      var route = c.getDefaultVrf().getStaticRoutes().first();
      assertEquals(120, route.getAdministrativeCost());
      assertEquals(7, route.getTag());
      assertEquals(NextHopDiscard.instance(), route.getNextHop());
      assertEquals(60, c.getVrfs().get("blue").getStaticRoutes().first().getAdministrativeCost());
    }
  }
}
