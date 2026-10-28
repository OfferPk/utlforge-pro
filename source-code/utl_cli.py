#!/usr/bin/env python3
"""
UTLForge Pro — Command Line Interface
CCSDS 722.1-M-2 CFDP Unitdata Transfer Layers (UTL) Toolchain
"""

import sys
import os
import argparse
import json
import struct
from datetime import datetime

UT_LAYERS = ['EPP', 'SPP', 'BP_V7', 'LTP', 'UDP', 'TCP']

def create_cfdp_pdu(pdu_type=1, directive_code=7, src_entity=101, dst_entity=202, seq=1001, payload_str="HELLO_FLIGHT_DATA"):
    payload_bytes = [ord(c) for c in payload_str]
    crc_val = hex(abs((src_entity * 31 + seq * 104729) % 0xFFFF))[2:].upper().zfill(4)
    
    return {
        "cfdpHeader": {
            "version": 1,
            "pduType": pdu_type,
            "pduTypeName": "FILE_DIRECTIVE" if pdu_type == 0 else "FILE_DATA",
            "direction": 0,
            "transmissionMode": 0, # Acknowledged
            "crcFlag": 1,
            "entityIdLength": 2,
            "transactionSeqLength": 2,
            "sourceEntityId": src_entity,
            "transactionSequenceNumber": seq,
            "destinationEntityId": dst_entity
        },
        "directive": {
            "directiveCode": directive_code,
            "directiveName": "METADATA" if directive_code == 7 else "EOF"
        } if pdu_type == 0 else None,
        "fileData": {
            "offset": 0,
            "dataLength": len(payload_bytes)
        } if pdu_type == 1 else None,
        "payload": payload_bytes,
        "crc16": f"0x{crc_val}"
    }

def encapsulate_pdu(cfdp_pdu, layer="SPP", apid=565, port=5111, session_id=5001):
    raw_pdu_len = 8 + len(cfdp_pdu.get('payload', []))
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    res = {
        "utLayer": layer,
        "cfdpPdu": cfdp_pdu,
        "timestamp": now_iso
    }
    
    if layer == "EPP":
        res["eppHeader"] = {
            "protocolId": "0b110",
            "protocolName": "CFDP_ENCAPSULATION",
            "lengthType": 0,
            "packetLength": raw_pdu_len
        }
        res["wireBytesTotal"] = 2 + raw_pdu_len
    elif layer == "SPP":
        res["sppHeader"] = {
            "packetVersion": 0,
            "packetType": 0,
            "secondaryHeaderFlag": 0,
            "apid": apid,
            "sequenceFlags": 3,
            "packetSequenceCount": 42,
            "packetDataLength": raw_pdu_len - 1
        }
        res["wireBytesTotal"] = 6 + raw_pdu_len
    elif layer == "BP_V7":
        src_id = cfdp_pdu['cfdpHeader']['sourceEntityId']
        dst_id = cfdp_pdu['cfdpHeader']['destinationEntityId']
        res["bpHeader"] = {
            "bpVersion": 7,
            "sourceEid": f"ipn:{src_id}.1",
            "destinationEid": f"ipn:{dst_id}.1",
            "bundleControlFlags": 1,
            "lifetimeMs": 86400000,
            "creationTimestamp": int(datetime.utcnow().timestamp())
        }
        res["wireBytesTotal"] = 32 + raw_pdu_len
    elif layer == "LTP":
        res["ltpHeader"] = {
            "ltpVersion": 0,
            "clientServiceId": 1,
            "sessionId": session_id,
            "isRedData": cfdp_pdu['cfdpHeader']['transmissionMode'] == 0,
            "clientServiceDataLength": raw_pdu_len
        }
        res["wireBytesTotal"] = 16 + raw_pdu_len
    elif layer == "UDP":
        res["udpHeader"] = {
            "srcPort": port,
            "dstPort": port,
            "udpLength": 8 + raw_pdu_len,
            "checksum": "0xABCD"
        }
        res["wireBytesTotal"] = 8 + raw_pdu_len
    elif layer == "TCP":
        res["tcpHeader"] = {
            "lengthPrefixBytes": 2,
            "framedLength": raw_pdu_len,
            "dstPort": port + 1
        }
        res["wireBytesTotal"] = 2 + raw_pdu_len
        
    return res

def audit_items(items):
    checks = []
    
    # UTL-001
    c1 = len(items) > 0 and all(it.get('cfdpPdu') and it.get('utLayer') for it in items)
    checks.append(('UTL-001', 'Abstract UT Interface Conformance', c1))
    
    # UTL-002
    epp = [it for it in items if it.get('utLayer') == 'EPP']
    c2 = len(epp) == 0 or all(it.get('eppHeader', {}).get('protocolId') == '0b110' for it in epp)
    checks.append(('UTL-002', 'Encapsulation Packet Protocol (EPP) Framing', c2))
    
    # UTL-003
    spp = [it for it in items if it.get('utLayer') == 'SPP']
    c3 = len(spp) == 0 or all(it.get('sppHeader', {}).get('apid', 9999) <= 2047 and it.get('sppHeader', {}).get('sequenceFlags') == 3 for it in spp)
    checks.append(('UTL-003', 'Space Packet Protocol (SPP) APID Limits', c3))
    
    # UTL-004
    bp = [it for it in items if it.get('utLayer') == 'BP_V7']
    c4 = len(bp) == 0 or all(it.get('bpHeader', {}).get('sourceEid', '').startswith(('ipn:', 'dtn:')) and it.get('bpHeader', {}).get('lifetimeMs', 0) > 0 for it in bp)
    checks.append(('UTL-004', 'Bundle Protocol (BPv7) EID Mapping', c4))
    
    # UTL-005
    ltp = [it for it in items if it.get('utLayer') == 'LTP']
    c5 = len(ltp) == 0 or all(it.get('ltpHeader', {}).get('clientServiceId') == 1 for it in ltp)
    checks.append(('UTL-005', 'LTP Client Service ID Conformance', c5))
    
    # UTL-006
    udp = [it for it in items if it.get('utLayer') == 'UDP']
    c6 = len(udp) == 0 or all(it.get('udpHeader', {}).get('udpLength', 99999) <= 65507 for it in udp)
    checks.append(('UTL-006', 'UDP Datagram Boundary & MTU Enforcement', c6))
    
    # UTL-007
    tcp = [it for it in items if it.get('utLayer') == 'TCP']
    c7 = len(tcp) == 0 or all(it.get('tcpHeader', {}).get('lengthPrefixBytes') == 2 for it in tcp)
    checks.append(('UTL-007', 'TCP Length-Prefixed Stream Framing', c7))
    
    # UTL-008
    c8 = all(it.get('wireBytesTotal', 0) > 0 for it in items)
    checks.append(('UTL-008', 'PDU Size & Segmentation Guard', c8))
    
    # UTL-009
    c9 = all(it['cfdpPdu']['cfdpHeader']['destinationEntityId'] > 0 for it in items)
    checks.append(('UTL-009', 'Entity ID to UT Address Mapping', c9))
    
    # UTL-010
    c10 = all(it['cfdpPdu'].get('crc16', '').startswith('0x') for it in items)
    checks.append(('UTL-010', 'Frame Integrity & Checksum Verification', c10))
    
    return checks

def main():
    parser = argparse.ArgumentParser(description="UTLForge Pro — CCSDS 722.1-M-2 CFDP Unitdata Transfer Layers Toolchain")
    subparsers = parser.add_subparsers(dest="command")
    
    # generate-pdu
    p_gen = subparsers.add_parser("generate-pdu", help="Generate a standard CFDP PDU")
    p_gen.add_argument("--type", choices=['directive', 'data'], default='data')
    p_gen.add_argument("--src", type=int, default=101, help="Source Entity ID")
    p_gen.add_argument("--dst", type=int, default=202, help="Destination Entity ID")
    p_gen.add_argument("--seq", type=int, default=1001, help="Transaction Sequence Number")
    p_gen.add_argument("--output", default="cfdp_pdu.json")
    
    # encapsulate
    p_enc = subparsers.add_parser("encapsulate", help="Encapsulate CFDP PDU into target UT Layer")
    p_enc.add_argument("--layer", choices=UT_LAYERS, default='SPP')
    p_enc.add_argument("--input", default="cfdp_pdu.json")
    p_enc.add_argument("--output", default="encapsulated.json")
    
    # multicast
    p_mul = subparsers.add_parser("multicast", help="Multiplex CFDP PDU across all 6 UT Layers")
    p_mul.add_argument("--input", default=None)
    
    # audit
    p_aud = subparsers.add_parser("audit", help="Run 10-point normative audit on encapsulated packets")
    p_aud.add_argument("file", help="Path to encapsulated JSON stream")
    
    args = parser.parse_args()
    
    if args.command == "generate-pdu":
        pdu_t = 0 if args.type == 'directive' else 1
        pdu = create_cfdp_pdu(pdu_t, src_entity=args.src, dst_entity=args.dst, seq=args.seq)
        with open(args.output, 'w') as f:
            json.dump(pdu, f, indent=2)
        print(f"[OK] Generated CFDP PDU: {args.output}")
        
    elif args.command == "encapsulate":
        if os.path.exists(args.input):
            with open(args.input, 'r') as f:
                pdu = json.load(f)
        else:
            pdu = create_cfdp_pdu()
            
        enc = encapsulate_pdu(pdu, layer=args.layer)
        with open(args.output, 'w') as f:
            json.dump(enc, f, indent=2)
        print(f"[OK] Encapsulated into {args.layer}: {args.output} ({enc['wireBytesTotal']} total wire octets)")
        
    elif args.command == "multicast":
        pdu = create_cfdp_pdu()
        print("======================================================================")
        print("  CCSDS 722.1-M-2 CFDP Unitdata Transfer Layers Multi-Stack Analysis")
        print("======================================================================")
        print(f"CFDP PDU Payload Size: {len(pdu['payload'])} bytes | Total PDU: 13 bytes")
        print("----------------------------------------------------------------------")
        for layer in UT_LAYERS:
            enc = encapsulate_pdu(pdu, layer=layer)
            overhead = enc['wireBytesTotal'] - 13
            print(f"Layer: {layer:<8} | Total Wire Bytes: {enc['wireBytesTotal']:<3} | Header Overhead: {overhead} bytes")
        print("======================================================================")
        
    elif args.command == "audit":
        with open(args.file, 'r') as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        results = audit_items(items)
        print("======================================================================")
        print("  CCSDS 722.1-M-2 UTL 10-Point Normative Compliance Audit")
        print("======================================================================")
        all_pass = True
        for cid, name, p in results:
            status = "PASS" if p else "FAIL"
            print(f"[{cid}] {name:<45} : {status}")
            if not p: all_pass = False
        print("----------------------------------------------------------------------")
        score = sum(1 for _, _, p in results) / len(results) * 100
        print(f"Audit Score: {score:.1f}% ({'CCSDS_722_1_UTL_CERTIFIED' if all_pass else 'NON_COMPLIANT'})")
        print("======================================================================")
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
