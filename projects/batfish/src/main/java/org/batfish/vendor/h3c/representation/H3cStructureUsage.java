package org.batfish.vendor.h3c.representation;

import org.batfish.vendor.StructureUsage;

public enum H3cStructureUsage implements StructureUsage {
  INTERFACE_VPN("interface VPN binding"),
  AGGREGATE_MEMBER("aggregate member"),
  INTERFACE_ISIS("interface ISIS process"),
  BGP_VPN("BGP VPN"),
  BGP_SOURCE("BGP source interface"),
  BGP_POLICY("BGP route-policy"),
  POLICY_MATCH("route-policy match"),
  REDISTRIBUTION_POLICY("redistribution route-policy"),
  STATIC_VPN("static route VPN"),
  STATIC_INTERFACE("static route interface"),
  INTERFACE_VSI("interface VSI"),
  EVPN_AC("EVPN attachment circuit"),
  SRV6_LOCATOR("SRv6 locator");

  private final String _description;

  H3cStructureUsage(String description) {
    _description = description;
  }

  @Override
  public String getDescription() {
    return _description;
  }
}
