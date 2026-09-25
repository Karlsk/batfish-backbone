from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.contracts.base import Contract

# Fixed engine catalogs: NodePropertySpecifier and InterfacePropertySpecifier.
NodeProperty = Literal[
    "AS_Path_Access_Lists",
    "Authentication_Key_Chains",
    "Community_Match_Exprs",
    "Community_Set_Exprs",
    "Community_Set_Match_Exprs",
    "Community_Sets",
    "Configuration_Format",
    "Default_Cross_Zone_Action",
    "Default_Inbound_Action",
    "DNS_Servers",
    "DNS_Source_Interface",
    "Domain_Name",
    "Hostname",
    "IKE_Phase1_Keys",
    "IKE_Phase1_Policies",
    "IKE_Phase1_Proposals",
    "Interfaces",
    "IP_Access_Lists",
    "IP6_Access_Lists",
    "IPsec_Peer_Configs",
    "IPsec_Phase2_Policies",
    "IPsec_Phase2_Proposals",
    "Logging_Servers",
    "Logging_Source_Interface",
    "NTP_Servers",
    "NTP_Source_Interface",
    "PBR_Policies",
    "Route_Filter_Lists",
    "Route6_Filter_Lists",
    "Routing_Policies",
    "SNMP_Source_Interface",
    "SNMP_Trap_Servers",
    "TACACS_Servers",
    "TACACS_Source_Interface",
    "VRFs",
    "Zones",
]
InterfaceProperty = Literal[
    "Access_VLAN",
    "Active",
    "Admin_Up",
    "Allowed_VLANs",
    "All_Prefixes",
    "Auto_State_VLAN",
    "Bandwidth",
    "Blacklisted",
    "Channel_Group",
    "Channel_Group_Members",
    "Declared_Names",
    "Description",
    "DHCP_Relay_Addresses",
    "Encapsulation_VLAN",
    "HSRP_Groups",
    "HSRP_Version",
    "Inactive_Reason",
    "Incoming_Filter_Name",
    "Interface_Type",
    "MLAG_ID",
    "MTU",
    "Native_VLAN",
    "Outgoing_Filter_Name",
    "PBR_Policy_Name",
    "Primary_Address",
    "Primary_Network",
    "Proxy_ARP",
    "Rip_Enabled",
    "Rip_Passive",
    "Spanning_Tree_Portfast",
    "Speed",
    "Switchport",
    "Switchport_Mode",
    "Switchport_Trunk_Encapsulation",
    "VRF",
    "VRRP_Groups",
    "Zone_Name",
]

Name = Annotated[
    str, StringConstraints(min_length=1, max_length=255, pattern=r"^[^\x00-\x1f\x7f]+$")
]
Expression = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
]


class LiteralSelector(Contract):
    mode: Literal["literal"]
    values: tuple[Name, ...] = Field(min_length=1, max_length=100)


class ExpressionSelector(Contract):
    mode: Literal["expression"]
    expression: Expression


Selector = Annotated[LiteralSelector | ExpressionSelector, Field(discriminator="mode")]


class NodeOptions(Contract):
    nodes: Selector | None = None
    properties: tuple[NodeProperty, ...] = Field(
        default=("Hostname", "Configuration_Format", "Interfaces"), min_length=1, max_length=100
    )


class NodesRequest(Contract):
    options: NodeOptions = Field(default_factory=NodeOptions)


class InterfaceOptions(Contract):
    interfaces: Selector | None = None
    properties: tuple[InterfaceProperty, ...] = Field(
        default=("Description", "Active", "Primary_Address", "VRF"), min_length=1, max_length=100
    )


class InterfacesRequest(Contract):
    nodes: Selector | None = None
    options: InterfaceOptions = Field(default_factory=InterfaceOptions)
