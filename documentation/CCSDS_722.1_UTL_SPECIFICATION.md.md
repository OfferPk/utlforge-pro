# CCSDS 722.1-M-2 CFDP Unitdata Transfer Layers (UTL) Specification

## Technical Reference, Protocol Adaptors & Multi-Stack Multiplexing

### 1\. Executive Summary & Purpose

The **CCSDS File Delivery Protocol (CFDP)**, defined in **CCSDS 727.0-B-5**, is the international standard for transferring files to, from, and between spacecraft across long-delay, high-noise, and intermittently connected space links. CFDP functions at the application/middleware layer, transferring files reliably (Class 2 Acknowledged) or best-effort (Class 1 Unacknowledged).

However, CFDP does not define its own physical transmission framing. Instead, it interfaces with an abstract lower layer called the **Unitdata Transfer (UT) Layer** via two primitives:

- `UT_UNITDATA.request (CFDP PDU, Destination UT Address)`  
- `UT_UNITDATA.indication (CFDP PDU, Source UT Address)`

Until the release of **CCSDS 722.1-M-2 (Magenta Book, Issue 2, July 2026\)**, every space agency and mission implementation utilized custom, non-standardized adapters to bridge CFDP onto physical radio links. CCSDS 722.1 specifies the normative mapping, encapsulation headers, and addressing resolution rules for CFDP over six distinct space and terrestrial transport stacks:

1. **CCSDS Encapsulation Packet Protocol (EPP)** — CCSDS 133.1-B-3  
2. **CCSDS Space Packet Protocol (SPP)** — CCSDS 133.0-B-2  
3. **CCSDS Bundle Protocol v7 (BPv7)** — CCSDS 734.2-B-1 / RFC 9171  
4. **CCSDS Licklider Transmission Protocol (LTP)** — CCSDS 734.1-B-1 / RFC 5326  
5. **User Datagram Protocol (UDP/IP)** — RFC 768  
6. **Transmission Control Protocol (TCP/IP)** — RFC 793 with explicit length-prefixing

---

### 2\. Multi-Stack Encapsulation Mappings

#### 2.1 CFDP over Encapsulation Packet Protocol (EPP)

- **Protocol ID**: 3-bit Protocol ID field set to `0b110` (Direct CFDP encapsulation per SANA).  
- **Framing**: Lightweight encapsulation adding only 1 to 4 octets of header overhead.  
- **Application**: Direct transmission over CCSDS Space Data Link Protocols (USLP, AOS, TM/TC) without APID multiplexing.

#### 2.2 CFDP over Space Packet Protocol (SPP)

- **Primary Header**: 6 octets (Packet Version \= 0, Type \= 0/1, SecHdrFlag \= 0, APID \= 11-bit, Sequence Flags \= `0b11` unsegmented user data, Packet Data Length).  
- **APID Allocation**: Dedicated Application Process Identifier (e.g. `0x0235` or SANA assigned) allocated to CFDP entity instances.  
- **Application**: Traditional satellite command & telemetry buses (NASA cFS, SCOS-2000, Yamcs).

#### 2.3 CFDP over Bundle Protocol v7 (BPv7)

- **Endpoint Identifiers (EID)**: Formatted as URIs using the `ipn:` scheme (`ipn:node.service`, e.g. `ipn:101.1`) or `dtn:` scheme.  
- **Block Formatting**: CFDP PDU encapsulated directly into the BP Payload Block.  
- **Custody & DTN**: Leverages BPv7 storage-routing across multi-hop interplanetary networks (LunaNet, Mars Relays).

#### 2.4 CFDP over Licklider Transmission Protocol (LTP)

- **Client Service ID**: SANA-assigned Client Service ID `1` for CFDP.  
- **Block Segregation**:  
  - CFDP Class 2 (Ack) mapped to **LTP Red Blocks** (retransmitted upon loss).  
  - CFDP Class 1 (Unack) mapped to **LTP Green Blocks** (unacknowledged transmission).

#### 2.5 CFDP over UDP/IP

- **Datagram Envelope**: CFDP PDU encapsulated into UDP payload with dedicated port (default `5111`).  
- **MTU Enforcement**: Maximum payload size capped at 65,507 octets to eliminate IP fragmentation risks.

#### 2.6 CFDP over TCP/IP

- **Stream Framing**: Explicit 2-byte (or 4-byte) big-endian length prefix prepended to each CFDP PDU.  
- **Stream Coalescing Elimination**: Solves TCP socket byte-stream merging by guaranteeing packet delineation on receiving endpoints.

---

### 3\. Header Overhead & Protocol Efficiency Analysis

| UT Layer Protocol | Standard Reference | Header Overhead | Key Addressing Identifier | Primary Operational Domain |
| :---- | :---: | :---: | :---- | :---- |
| **EPP** | CCSDS 133.1-B-3 | 2 Bytes | Protocol ID `0b110` | Direct Space Data Link (USLP/AOS) |
| **SPP** | CCSDS 133.0-B-2 | 6 Bytes | 11-Bit APID (e.g. `0x0235`) | Satellite Bus Telemetry / Telecommand |
| **BPv7** | CCSDS 734.2-B-1 | 32 Bytes | RFC 9171 EID (`ipn:101.1`) | Cislunar & Interplanetary DTN |
| **LTP** | CCSDS 734.1-B-1 | 16 Bytes | Client Service ID `1` | Deep-Space Point-to-Point Long Delay |
| **UDP/IP** | RFC 768 | 8 Bytes | IP Address \+ Port 5111 | Ground Station LAN / EGSE Testbed |
| **TCP/IP** | RFC 793 | 2 Bytes | Length-Prefix \+ Port 5112 | Reliable Ground Station WAN Relays |

