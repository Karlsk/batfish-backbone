package org.batfish.vendor.h3c.representation;

import org.batfish.vendor.StructureType;

public enum H3cStructureType implements StructureType {
  INTERFACE("interface"),
  VPN("vpn-instance"),
  ISIS("isis process"),
  BGP("bgp instance"),
  ROUTE_POLICY("route-policy"),
  PREFIX_LIST("ip prefix-list"),
  IPV6_PREFIX_LIST("ipv6 prefix-list"),
  COMMUNITY_LIST("community-list"),
  EXTCOMMUNITY_LIST("extcommunity-list"),
  RD_LIST("rd-list"),
  VSI("vsi"),
  XCONNECT("xconnect-group"),
  LOCATOR("srv6 locator");

  private final String _description;

  H3cStructureType(String description) {
    _description = description;
  }

  @Override
  public String getDescription() {
    return _description;
  }
}
