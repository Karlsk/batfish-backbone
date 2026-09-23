package org.batfish.vendor.h3c.representation;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.ConfigurationFormat;
import org.batfish.datamodel.Ip;
import org.batfish.vendor.VendorConfiguration;

/** H3C Comware vendor model; see {@link H3cConversions} for the phase-one VI boundary. */
public final class H3cConfiguration extends VendorConfiguration {
  private String _hostname;
  private Ip _routerId;
  private final Map<String, H3cModel.Interface> _interfaces = new LinkedHashMap<>();
  private final Map<String, H3cModel.Vpn> _vpns = new LinkedHashMap<>();
  private final List<H3cModel.StaticRoute> _staticRoutes = new ArrayList<>();
  private final List<H3cStatement> _ipv6StaticRoutes = new ArrayList<>();
  private final Map<Integer, H3cModel.Isis> _isis = new TreeMap<>();
  private final List<H3cModel.Bgp> _bgp = new ArrayList<>();
  private final Map<String, H3cModel.Policy> _policies = new LinkedHashMap<>();
  private final Map<String, Map<Integer, H3cModel.PrefixEntry>> _prefixLists =
      new LinkedHashMap<>();
  private final Map<String, List<H3cStatement>> _ipv6PrefixLists = new LinkedHashMap<>();
  private final Map<String, Map<Integer, H3cModel.CommunityEntry>> _communities =
      new LinkedHashMap<>();
  private final Map<String, Map<Integer, H3cModel.CommunityEntry>> _extcommunities =
      new LinkedHashMap<>();
  private final Map<String, List<H3cStatement>> _rdLists = new LinkedHashMap<>();
  private final Map<String, H3cModel.Evpn> _vsis = new LinkedHashMap<>();
  private final Map<String, H3cModel.Evpn> _xconnects = new LinkedHashMap<>();
  private final Map<String, H3cStatement> _locators = new LinkedHashMap<>();
  private final List<H3cStatement> _retained = new ArrayList<>();

  public Map<String, H3cModel.Interface> getInterfaces() {
    return _interfaces;
  }

  public Map<String, H3cModel.Vpn> getVpns() {
    return _vpns;
  }

  public List<H3cModel.StaticRoute> getStaticRoutes() {
    return _staticRoutes;
  }

  public List<H3cStatement> getIpv6StaticRoutes() {
    return _ipv6StaticRoutes;
  }

  public Map<Integer, H3cModel.Isis> getIsisProcesses() {
    return _isis;
  }

  public List<H3cModel.Bgp> getBgpProcesses() {
    return _bgp;
  }

  public Map<String, H3cModel.Policy> getPolicies() {
    return _policies;
  }

  public Map<String, Map<Integer, H3cModel.PrefixEntry>> getPrefixLists() {
    return _prefixLists;
  }

  public Map<String, List<H3cStatement>> getIpv6PrefixLists() {
    return _ipv6PrefixLists;
  }

  public Map<String, Map<Integer, H3cModel.CommunityEntry>> getCommunities() {
    return _communities;
  }

  public Map<String, Map<Integer, H3cModel.CommunityEntry>> getExtcommunities() {
    return _extcommunities;
  }

  public Map<String, List<H3cStatement>> getRdLists() {
    return _rdLists;
  }

  public Map<String, H3cModel.Evpn> getVsis() {
    return _vsis;
  }

  public Map<String, H3cModel.Evpn> getXconnects() {
    return _xconnects;
  }

  public Map<String, H3cStatement> getLocators() {
    return _locators;
  }

  public List<H3cStatement> getRetained() {
    return _retained;
  }

  public Ip getRouterId() {
    return _routerId;
  }

  public void setRouterId(Ip routerId) {
    _routerId = routerId;
  }

  @Override
  public String getHostname() {
    return _hostname;
  }

  @Override
  public void setHostname(String hostname) {
    _hostname = hostname.toLowerCase(Locale.ROOT);
  }

  @Override
  public void setVendor(ConfigurationFormat format) {}

  @Override
  public List<Configuration> toVendorIndependentConfigurations() {
    Configuration c = H3cConversions.convert(this);
    for (H3cStructureType type : H3cStructureType.values()) {
      markConcreteStructure(type);
    }
    return List.of(c);
  }
}
