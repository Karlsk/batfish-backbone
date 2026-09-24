package org.batfish.vendor.huawei.representation;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.batfish.datamodel.Configuration;
import org.batfish.datamodel.ConfigurationFormat;
import org.batfish.datamodel.Ip;
import org.batfish.vendor.VendorConfiguration;

/** Huawei VRP vendor model; see {@link HuaweiConversions} for the phase-one VI boundary. */
public final class HuaweiConfiguration extends VendorConfiguration {
  private String _hostname;
  private Ip _routerId;
  private String _dcnVpn;

  public String getDcnVpn() {
    return _dcnVpn;
  }

  public void setDcnVpn(String name) {
    _dcnVpn = name;
  }

  private final Map<String, HuaweiModel.Interface> _interfaces = new LinkedHashMap<>();
  private final Map<String, HuaweiModel.Vpn> _vpns = new LinkedHashMap<>();
  private final List<HuaweiModel.StaticRoute> _staticRoutes = new ArrayList<>();
  private final List<HuaweiStatement> _ipv6StaticRoutes = new ArrayList<>();
  private final Map<Integer, HuaweiModel.Isis> _isis = new TreeMap<>();
  private final List<HuaweiModel.Bgp> _bgp = new ArrayList<>();
  private final Map<String, HuaweiModel.Policy> _policies = new LinkedHashMap<>();
  private final Map<String, Map<Integer, HuaweiModel.PrefixEntry>> _prefixLists =
      new LinkedHashMap<>();
  private final Map<String, List<HuaweiStatement>> _ipv6PrefixLists = new LinkedHashMap<>();
  private final Map<String, Map<Integer, HuaweiModel.CommunityEntry>> _communities =
      new LinkedHashMap<>();
  private final Map<String, Map<Integer, HuaweiModel.CommunityEntry>> _extcommunities =
      new LinkedHashMap<>();
  private final Set<String> _invalidCommunities = new LinkedHashSet<>();
  private final Set<String> _invalidExtcommunities = new LinkedHashSet<>();
  private final Map<String, List<HuaweiStatement>> _rdLists = new LinkedHashMap<>();
  private final Map<String, HuaweiModel.Evpn> _evpnInstances = new LinkedHashMap<>();
  private final Map<String, HuaweiModel.Evpn> _evpls = new LinkedHashMap<>();
  private final Map<String, HuaweiModel.Locator> _locators = new LinkedHashMap<>();
  private final Map<Integer, HuaweiModel.Evpn> _bridgeDomains = new LinkedHashMap<>();
  private final List<HuaweiStatement> _ospf = new ArrayList<>();
  private final List<HuaweiStatement> _retained = new ArrayList<>();
  private final List<HuaweiModel.UnsupportedRedistribution> _unsupportedRedistributions =
      new ArrayList<>();

  public List<HuaweiModel.UnsupportedRedistribution> getUnsupportedRedistributions() {
    return _unsupportedRedistributions;
  }

  public Map<String, HuaweiModel.Interface> getInterfaces() {
    return _interfaces;
  }

  public Map<String, HuaweiModel.Vpn> getVpns() {
    return _vpns;
  }

  public List<HuaweiModel.StaticRoute> getStaticRoutes() {
    return _staticRoutes;
  }

  public List<HuaweiStatement> getIpv6StaticRoutes() {
    return _ipv6StaticRoutes;
  }

  public Map<Integer, HuaweiModel.Isis> getIsisProcesses() {
    return _isis;
  }

  public List<HuaweiModel.Bgp> getBgpProcesses() {
    return _bgp;
  }

  public Map<String, HuaweiModel.Policy> getPolicies() {
    return _policies;
  }

  public Map<String, Map<Integer, HuaweiModel.PrefixEntry>> getPrefixLists() {
    return _prefixLists;
  }

  public Map<String, List<HuaweiStatement>> getIpv6PrefixLists() {
    return _ipv6PrefixLists;
  }

  public Map<String, Map<Integer, HuaweiModel.CommunityEntry>> getCommunities() {
    return _communities;
  }

  public Map<String, Map<Integer, HuaweiModel.CommunityEntry>> getExtcommunities() {
    return _extcommunities;
  }

  public Set<String> getInvalidCommunities() {
    return _invalidCommunities;
  }

  public Set<String> getInvalidExtcommunities() {
    return _invalidExtcommunities;
  }

  public Map<String, List<HuaweiStatement>> getRdLists() {
    return _rdLists;
  }

  public Map<String, HuaweiModel.Evpn> getEvpnInstances() {
    return _evpnInstances;
  }

  public Map<String, HuaweiModel.Evpn> getEvpls() {
    return _evpls;
  }

  public Map<Integer, HuaweiModel.Evpn> getBridgeDomains() {
    return _bridgeDomains;
  }

  public List<HuaweiStatement> getOspfProcesses() {
    return _ospf;
  }

  public Map<String, HuaweiModel.Locator> getLocators() {
    return _locators;
  }

  public List<HuaweiStatement> getRetained() {
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
    Configuration c = HuaweiConversions.convert(this);
    for (HuaweiStructureType type : HuaweiStructureType.values()) {
      markConcreteStructure(type);
    }
    return List.of(c);
  }
}
