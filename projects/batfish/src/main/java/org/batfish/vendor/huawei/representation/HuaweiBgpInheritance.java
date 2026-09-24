package org.batfish.vendor.huawei.representation;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeSet;

/** Resolves effective IPv4 peers without mutating transport or other address-family state. */
public final class HuaweiBgpInheritance {
  public static Map<String, HuaweiModel.Peer> ipv4Peers(HuaweiModel.BgpVrf base) {
    HuaweiModel.BgpVrf af = base.families.get("ipv4-family unicast");
    Map<String, HuaweiModel.Peer> result = new LinkedHashMap<>();
    TreeSet<String> names = new TreeSet<>(base.peers.keySet());
    if (af != null) {
      names.addAll(af.peers.keySet());
    }
    for (String name : names) {
      HuaweiModel.Peer member = base.peers.get(name);
      HuaweiModel.Peer afMember = af == null ? null : af.peers.get(name);
      String group =
          afMember != null && afMember.group != null
              ? afMember.group
              : member == null ? null : member.group;
      HuaweiModel.Peer p = new HuaweiModel.Peer();
      overlay(p, base.groups.get(group));
      overlay(p, member);
      if (af != null) {
        overlay(p, af.groups.get(group));
        overlay(p, afMember);
      }
      // VRP automatically activates IPv4 transport peers; undo enable is an explicit override.
      if (p.enabled == null) {
        p.enabled = true;
      }
      if (p.shutdown == null) {
        p.shutdown = false;
      }
      if (p.multihop == null) {
        p.multihop = false;
      }
      if (p.reflectClient == null) {
        p.reflectClient = false;
      }
      if (p.sendCommunity == null) {
        p.sendCommunity = false;
      }
      if (p.sendExtendedCommunity == null) {
        p.sendExtendedCommunity = false;
      }
      if (p.replaceAs == null) {
        p.replaceAs = false;
      }
      if (p.nextHopSelf == null) {
        p.nextHopSelf = false;
      }
      if (p.allowAs == null) {
        p.allowAs = 0;
      }
      result.put(name, p);
    }
    return result;
  }

  private static void overlay(HuaweiModel.Peer p, HuaweiModel.Peer v) {
    if (v == null) {
      return;
    }
    if (v.remoteAs != null) {
      p.remoteAs = v.remoteAs;
    }
    if (v.description != null) {
      p.description = v.description;
    }
    if (v.sourceInterface != null) {
      p.sourceInterface = v.sourceInterface;
      // Null explicitly means infer from the overriding interface, not inherit an old IP.
      p.sourceIp = v.sourceIp;
    }
    if (v.enabled != null) {
      p.enabled = v.enabled;
    }
    if (v.shutdown != null) {
      p.shutdown = v.shutdown;
    }
    if (v.multihop != null) {
      p.multihop = v.multihop;
    }
    if (v.reflectClient != null) {
      p.reflectClient = v.reflectClient;
    }
    if (v.sendCommunity != null) {
      p.sendCommunity = v.sendCommunity;
    }
    if (v.sendExtendedCommunity != null) {
      p.sendExtendedCommunity = v.sendExtendedCommunity;
    }
    if (v.replaceAs != null) {
      p.replaceAs = v.replaceAs;
    }
    if (v.nextHopSelf != null) {
      p.nextHopSelf = v.nextHopSelf;
    }
    if (v.allowAs != null) {
      p.allowAs = v.allowAs;
    }
    if (v.importPolicy != null) {
      p.importPolicy = v.importPolicy;
    }
    if (v.exportPolicy != null) {
      p.exportPolicy = v.exportPolicy;
    }
    p.retained.addAll(v.retained);
  }

  private HuaweiBgpInheritance() {}
}
