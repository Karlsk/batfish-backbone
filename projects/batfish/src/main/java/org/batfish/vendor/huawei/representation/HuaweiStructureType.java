package org.batfish.vendor.huawei.representation;

import org.batfish.vendor.StructureType;

public enum HuaweiStructureType implements StructureType {
  INTERFACE("interface"),
  VPN("vpn-instance"),
  ISIS("isis process"),
  BGP("bgp instance"),
  ROUTE_POLICY("route-policy"),
  PREFIX_LIST("ip ip-prefix"),
  IPV6_PREFIX_LIST("ip ipv6-prefix"),
  COMMUNITY_LIST("community-filter"),
  EXTCOMMUNITY_LIST("extcommunity-filter"),
  RD_LIST("rd-filter"),
  EVPN("evpn instance"),
  EVPL("evpl instance"),
  BRIDGE_DOMAIN("bridge-domain"),
  BGP_GROUP("bgp peer group"),
  LOCATOR("srv6 locator");

  private final String _description;

  HuaweiStructureType(String description) {
    _description = description;
  }

  @Override
  public String getDescription() {
    return _description;
  }
}
