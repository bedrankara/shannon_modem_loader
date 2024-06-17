#!/bin/python3

# Samsung Shannon Modem Loader - PAL Reconstructor
# This script is autoamtically executed by the loader
# Alexander Pick 2024

import idc
import idaapi
import idautils
import ida_bytes
import ida_name
import ida_ua
import ida_struct
import ida_nalt
import ida_segment

import shannon_generic
import shannon_funcs

import os

# This code identifies a couple of functions of the platform abstraction layer and uses
# these to find the task table. This could be done in a much simpler fashion by searching
# for PALTskTm and work from there, but using the heuristic below a couple of func refs
# will be reconstructed and named which are quite important for future analysis
def find_pal_msg_funcs():

    idc.msg("[i] trying to identify PAL message related functions\n")

    # search only in main to avoid unnecessary long runtimes
    seg_t = ida_segment.get_segm_by_name("MAIN_file")

    pal_MsgSendTo_addr = shannon_generic.search_text(
        seg_t.start_ea, seg_t.end_ea, "PAL_MSG_MAX_ENTITY_COUNT")
    
    if (pal_MsgSendTo_addr != idaapi.BADADDR):
        # stupid hack to get beginning of the string since we found a substring
        # the PAL_MSG_MAX_ENTITY_COUNT string varies between BB versions so the 
        # search is for the most remarkable part only
        pal_MsgSendTo_addr = idc.prev_head(idc.next_head(pal_MsgSendTo_addr))

    # fallback for 5g versions which have the string slightly
    # crippled between hi/lo reg, furthermore the PAL_MSG_MAX_ENTITY_COUNT
    # string is in another function
    if (pal_MsgSendTo_addr == idaapi.BADADDR):
        pal_MsgSendTo_addr = shannon_generic.search_text(
            seg_t.start_ea, seg_t.end_ea, "QUEUE_NAME")

    # step 1 - find pal_MsgSendTo()
    if (pal_MsgSendTo_addr != idaapi.BADADDR):

        # realign if we are off by one here due to thumb and stuff
        if (pal_MsgSendTo_addr % 4):
            pal_MsgSendTo_addr += 1

        # most images have 2 xrefs to this string, ones is MsgSendTo
        for xref in idautils.XrefsTo(pal_MsgSendTo_addr, 0):

            func_start = idc.get_func_attr(xref.frm, idc.FUNCATTR_START)

            num_xrefs = len(list(idautils.XrefsTo(func_start, 0)))

            # pal_MsgSendTo has a lot of xrefs to itself, other candidate funcs don't have that
            if (num_xrefs > 15):

                pal_MsgSendTo_addr = func_start

                # sanity check - validate that xref target is a function, or next
                if (pal_MsgSendTo_addr == idaapi.BADADDR):
                    continue

                idc.msg("[i] pal_MsgSendTo(): %x\n" % pal_MsgSendTo_addr)
                ida_name.set_name(pal_MsgSendTo_addr, "pal_MsgSendTo",
                                  ida_name.SN_NOCHECK | ida_name.SN_FORCE)

        find_pal_msg_init(pal_MsgSendTo_addr)


# try to find pal_MsgInit() and a few others along
def find_pal_msg_init(pal_MsgSendTo_addr):
    # step2 - find pal_MsgInit()
    if (pal_MsgSendTo_addr != idaapi.BADADDR):

        func_cnt = 1
        tbl_cnt = 1
        pal_MsgInit_addr = pal_MsgSendTo_addr

        while (func_cnt < 12):

            # get a candidate get_prev_func returns a func_t :S
            pal_MsgInit_addr_t = idaapi.get_prev_func(pal_MsgInit_addr)
            pal_MsgInit_addr = pal_MsgInit_addr_t.start_ea

            que_init_addr = idc.next_head(pal_MsgInit_addr)

            # check if second opcode of function is a BL
            opcode = ida_ua.ua_mnem(que_init_addr)

            if (opcode == None):
                idc.msg("[e] found no opcode at %x\n" % pal_MsgInit_addr)
                continue

            # step3, find pal_QueInit to make sure we have the right parent function
            # A call to pal_QueInit is located directly after the reg save of pal_MsgInit
            if ("BL" in opcode):
                # yes, so we found pal_QueInit, get the target offset
                target_ref = idc.get_operand_value(que_init_addr, 0)

                idc.msg("[i] pal_QueInit(): %x\n" % target_ref)
                ida_name.set_name(target_ref, "pal_QueInit",
                                  ida_name.SN_NOCHECK)

                # low xp sidequest - find MsgDescriptorTbl (because we can)
                while (tbl_cnt < 5):

                    task_desc_offset = pal_MsgInit_addr + 4 + (4 * tbl_cnt)

                    opcode = ida_ua.ua_mnem(task_desc_offset)

                    if (opcode == "LDR"):
                        target_ref = idc.get_operand_value(task_desc_offset, 1)
                        target = int.from_bytes(
                            ida_bytes.get_bytes(target_ref, 4), "little")

                        idc.msg("[i] pal_MsgDescriptorTbl(): %x\n" % target)
                        ida_name.set_name(
                            target, "pal_MsgDescriptorTbl", ida_name.SN_NOCHECK)

                    tbl_cnt += 1

                idc.msg("[i] pal_MsgInit(): %x\n" % pal_MsgInit_addr)
                ida_name.set_name(pal_MsgInit_addr,
                                  "pal_MsgInit", ida_name.SN_NOCHECK)

                break

            func_cnt += 1

# try to find pal_Init()
def find_pal_init():
    
    idc.msg("[i] trying to identify PAL init and tasks\n")
   
    seg_t = ida_segment.get_segm_by_name("MAIN_file")
    
    pal_init_addr = shannon_generic.search_text(seg_t.start_ea, seg_t.end_ea, "UpTimer Init")
        
    for xref in idautils.XrefsTo(pal_init_addr, 0):
        
        idc.msg("[i] pal_Init xref: %x\n" % xref.frm)

        pal_init_addr = idc.get_func_attr(xref.frm, idc.FUNCATTR_START)
        
        if(pal_init_addr == idaapi.BADADDR):
            if(shannon_funcs.function_find_boundaries(xref.frm)):
                pal_init_addr = idc.get_func_attr(xref.frm, idc.FUNCATTR_START)

        idc.msg("[i] pal_Init(): %x\n" % pal_init_addr)
        ida_name.set_name(pal_init_addr, "pal_Init", ida_name.SN_NOCHECK)

        metrics = shannon_generic.get_metric(pal_init_addr)
        #shannon_generic.print_metrics(pal_init_addr, metrics)

        for branch in metrics[6]:
            first_operand = idc.get_operand_value(branch, 0)
            #idc.msg("[d] possible init function: %x\n" % branch)
            validate_if_task_scheduler(first_operand)
            #idc.msg("[d] possible dm_trace function: %x\n" % branch)
            validate_if_dm_trace_log(first_operand)

def validate_if_dm_trace_log(bl_target):

    metrics = shannon_generic.get_metric(bl_target)
    #shannon_generic.print_metrics(bl_target, metrics)

    # this function has an insane amount of xrefs, very unique
    if (len(metrics[4]) > 150000):
        idc.msg("[i] dm_TraceMsg(): %x\n" % bl_target)
        ida_name.set_name(bl_target, "dm_TraceMsg", ida_name.SN_NOCHECK)


# this function checks if the given function might be the task scheduler
def validate_if_task_scheduler(bl_target):

    init_func_start = idc.get_func_attr(bl_target, idc.FUNCATTR_START)
    init_func_end = idc.get_func_attr(bl_target, idc.FUNCATTR_END)

    if (init_func_start != idaapi.BADADDR and init_func_end != idaapi.BADADDR):

        init_func_cur = init_func_start

        while (1):
            init_func_cur = idc.next_head(init_func_cur)
            init_opcode = ida_ua.ua_mnem(init_func_cur)

            # bailout
            if (init_opcode == None):
                break

            if ("ADR" in init_opcode):
                init_adr_str = idc.get_operand_value(init_func_cur, 1)
                task_str = idc.get_strlit_contents(init_adr_str)
                if ("PALTskTm" in str(task_str)):
                    idc.msg("[i] pal_TaskMngrInit(): %x\n" % init_func_start)
                    ida_name.set_name(
                        init_func_start, "pal_TaskMngrInit", ida_name.SN_NOCHECK)
                    find_task_desc_tbl(init_func_start, init_func_end)
                    break

            # abort if nothing was found
            if (init_func_cur >= init_func_end):
                break

# step 6 - find the second LDR in the function. It is the TaskDescTbl
# TODO - only works for older modem versions, need fix for new
def find_task_desc_tbl(task_func_start, task_func_end):

    task_func_cur = task_func_start

    ldr_cnt = 0

    while (1):
        task_func_cur = idc.next_head(task_func_cur)
        task_opcode = ida_ua.ua_mnem(task_func_cur)
        
        # skip text chunks inside function
        if(task_opcode == None):
            #idc.msg("[d] error finding pal_TaskDescTbl() at %x\n" % task_func_cur)
            continue

        if ("LDR" in task_opcode):

            if (ldr_cnt == 1):
                target_ref = idc.get_operand_value(task_func_cur, 1)
                tbl_offset = int.from_bytes(
                    ida_bytes.get_bytes(target_ref, 4), "little")
                ida_name.set_name(
                    tbl_offset, "pal_TaskDescTbl", ida_name.SN_NOCHECK)

                idc.msg("[i] pal_TaskDescTbl(): %x\n" % tbl_offset)

                tasks = identify_task_init(tbl_offset)
                
                if(tasks < 5):
                    #retry the short version by deleting gap_14 (padding)

                    struct_id = ida_struct.get_struc_id("task_struct")
                    sptr = ida_struct.get_struc(struct_id)
                    str_ptr = ida_struct.get_member_by_name(sptr, "gap_14")
                    idaapi.del_struc_member(sptr, str_ptr.soff)
                    
                    tasks = identify_task_init(tbl_offset)

            ldr_cnt += 1

        # bailout
        if (task_func_cur >= task_func_end):
            break


def identify_task_init(tbl_offset):

    MAX_TASKS = 256
    tasks = 0

    struct_id = ida_struct.get_struc_id("task_struct")
    struct_size = ida_struct.get_struc_size(struct_id)
    sptr = ida_struct.get_struc(struct_id)

    while (tasks < MAX_TASKS):

        ida_bytes.del_items(tbl_offset, 0, struct_size)

        ida_bytes.create_struct(tbl_offset, struct_size, struct_id)

        str_ptr = ida_struct.get_member_by_name(sptr, "task_name")
        str_offset = int.from_bytes(ida_bytes.get_bytes(
            tbl_offset + str_ptr.soff, 4), "little")

        ida_bytes.create_strlit(str_offset, 0, ida_nalt.STRTYPE_C)

        task_name_str = idc.get_strlit_contents(str_offset)

        entry_ptr = ida_struct.get_member_by_name(sptr, "task_entry")
        entry_offset = int.from_bytes(ida_bytes.get_bytes(
            tbl_offset + entry_ptr.soff, 4), "little")

        # break early if we met an undefined entry
        if (entry_offset == 0x0):
            break

        task_entry_func_start = idc.get_func_attr(
            entry_offset, idc.FUNCATTR_START)

        if (task_entry_func_start != idaapi.BADADDR):

            idc.msg("[i] found task init for %s at %x\n" %
                    (str(task_name_str.decode()), task_entry_func_start))

            ida_name.set_name(task_entry_func_start, "pal_TaskInit_" + str(
                task_name_str.decode()), ida_name.SN_NOCHECK | ida_name.SN_FORCE)

        tbl_offset += struct_size

        tasks += 1

    return tasks

#for debugging purpose export SHANNON_WORKFLOW="NO"
if os.environ.get('SHANNON_WORKFLOW') == "NO":
    idc.msg("[i] running pal reconstruct in standalone mode\n")
    find_pal_msg_funcs()