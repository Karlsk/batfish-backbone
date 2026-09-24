package org.batfish.vendor.huawei.representation;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.batfish.datamodel.ConcreteInterfaceAddress;
import org.batfish.datamodel.IntegerSpace;
import org.batfish.datamodel.Ip;
import org.batfish.datamodel.Prefix;

/** Typed VRP configuration data. Unconverted commands retain their source statements. */
public final class HuaweiModel {
  public static final class Interface implements Serializable {
    public String name;
    public String description;
    public String vrf = "default";
    public boolean shutdown;
    public boolean bridge;
    public boolean trunk;
    public int accessVlan = 1;
    public IntegerSpace allowedVlans = IntegerSpace.of(1);
    public Integer mtu;
    public Integer vlan;
    public String aggregate;
    public Integer aggregateId;
    public final List<ConcreteInterfaceAddress> addresses = new ArrayList<>();
    public final List<String> ipv6Addresses = new ArrayList<>();
    public Integer isis;
    public Integer ipv6Isis;
    public String isisLevel = "level-1-2";
    public boolean isisP2p;
    public boolean isisSilent;
    public long isisCost = 10;
    public Long isisCostL1;
    public Long isisCostL2;
    public boolean isisBfd;
    public Long bfdMinimumInterval;
    public String evpn;
    public Integer bridgeDomain;
    public Integer evpl;
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Vpn implements Serializable {
    public String rd;
    public final Map<String, Evpn> families = new LinkedHashMap<>();
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class StaticRoute implements Serializable {
    public String vrf = "default";
    public Prefix network;
    public Ip nextHop;
    public String nextHopInterface;
    public String nextHopVrf;
    public int preference = 60;
    public long tag;
    public String description;
  }

  public record Redistribution(String policy, Long metric, boolean supported)
      implements Serializable {}

  public record UnsupportedRedistribution(String target, HuaweiStatement statement)
      implements Serializable {}

  public static final class Isis implements Serializable {
    public int id;
    public String net;
    public String vrf = "default";
    public String level = "level-1-2";
    public boolean overload;
    public boolean ipv4;
    public boolean ipv6;
    public boolean bfd;
    public Long bfdMinimumInterval;
    public final Map<String, Redistribution> redistribution = new LinkedHashMap<>();
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Bgp implements Serializable {
    public long asn;
    public String instance;
    public Ip routerId;
    public final Map<String, BgpVrf> vrfs = new LinkedHashMap<>();
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class BgpVrf implements Serializable {
    public Ip routerId;
    public final Map<String, Peer> peers = new LinkedHashMap<>();
    public final Map<String, Peer> groups = new LinkedHashMap<>();
    public final Map<String, BgpVrf> families = new LinkedHashMap<>();
    public int ebgpPreference = 255;
    public int ibgpPreference = 255;
    public int localPreference = 255;
    public final Map<String, Redistribution> redistribution = new LinkedHashMap<>();
    public boolean importDefaultRoute;
    public final Map<Prefix, String> networks = new LinkedHashMap<>();
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Peer implements Serializable {
    public String group;
    public Boolean reflectClient;
    public Long remoteAs;
    public String description;
    public String sourceInterface;
    public Ip sourceIp;
    public Boolean multihop;
    public Boolean enabled;
    public Boolean shutdown;
    public Boolean sendCommunity;
    public Boolean sendExtendedCommunity;
    public Boolean replaceAs;
    public Integer allowAs;
    public String importPolicy;
    public String exportPolicy;
    public Boolean nextHopSelf;
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Policy implements Serializable {
    public final Map<Integer, PolicyNode> nodes = new TreeMap<>();
  }

  public static final class PolicyNode implements Serializable {
    public boolean permit;
    public final Map<String, List<String>> matches = new LinkedHashMap<>();
    public final List<HuaweiStatement> actions = new ArrayList<>();
    public boolean unsupported;
  }

  public record PrefixEntry(boolean permit, Prefix prefix, int min, int max)
      implements Serializable {}

  public record CommunityEntry(boolean permit, boolean regex, List<String> values)
      implements Serializable {}

  public static final class Evpn implements Serializable {
    public String encapsulation;
    public String vpn;
    public Integer bridgeDomain;
    public String rd;
    public final List<String> importTargets = new ArrayList<>();
    public final List<String> exportTargets = new ArrayList<>();
    public String locator;
    public Long localServiceId;
    public Long remoteServiceId;
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Locator implements Serializable {
    public String prefix;
    public Integer prefixLength;
    public Integer staticLength;
    public final Map<String, Opcode> opcodes = new LinkedHashMap<>();
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  public static final class Opcode implements Serializable {
    public String function;
    public String interfaceName;
    public String vpn;
    public Integer bridgeDomain;
    public final List<HuaweiStatement> retained = new ArrayList<>();
  }

  private HuaweiModel() {}
}
