package org.batfish.vendor.h3c.representation;

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

/** Typed Comware configuration data. Unconverted commands retain their source statements. */
public final class H3cModel {
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
    public String vsi;
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  public static final class Vpn implements Serializable {
    public String rd;
    public final Map<String, Evpn> families = new LinkedHashMap<>();
    public final List<H3cStatement> retained = new ArrayList<>();
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

  public static final class Isis implements Serializable {
    public int id;
    public String net;
    public String level = "level-1-2";
    public boolean overload;
    public boolean ipv4;
    public boolean ipv6;
    public final Map<String, String> redistribution = new LinkedHashMap<>();
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  public static final class Bgp implements Serializable {
    public long asn;
    public String instance;
    public Ip routerId;
    public final Map<String, BgpVrf> vrfs = new LinkedHashMap<>();
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  public static final class BgpVrf implements Serializable {
    public Ip routerId;
    public final Map<String, Peer> peers = new LinkedHashMap<>();
    public final Map<String, String> redistribution = new LinkedHashMap<>();
    public final Map<Prefix, String> networks = new LinkedHashMap<>();
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  public static final class Peer implements Serializable {
    public Long remoteAs;
    public String description;
    public String sourceInterface;
    public Ip sourceIp;
    public boolean multihop;
    public boolean enabled;
    public boolean shutdown;
    public boolean sendCommunity;
    public boolean sendExtendedCommunity;
    public boolean replaceAs;
    public int allowAs;
    public String importPolicy;
    public String exportPolicy;
    public boolean nextHopSelf;
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  public static final class Policy implements Serializable {
    public final Map<Integer, PolicyNode> nodes = new TreeMap<>();
  }

  public static final class PolicyNode implements Serializable {
    public boolean permit;
    public final Map<String, List<String>> matches = new LinkedHashMap<>();
    public final List<H3cStatement> actions = new ArrayList<>();
    public boolean unsupported;
  }

  public record PrefixEntry(boolean permit, Prefix prefix, int min, int max)
      implements Serializable {}

  public record CommunityEntry(boolean permit, boolean regex, List<String> values)
      implements Serializable {}

  public static final class Evpn implements Serializable {
    public String encapsulation;
    public String rd;
    public final List<String> importTargets = new ArrayList<>();
    public final List<String> exportTargets = new ArrayList<>();
    public String locator;
    public Long color;
    public Long localServiceId;
    public Long remoteServiceId;
    public String attachmentCircuit;
    public final Map<String, Evpn> connections = new LinkedHashMap<>();
    public final List<H3cStatement> retained = new ArrayList<>();
  }

  private H3cModel() {}
}
