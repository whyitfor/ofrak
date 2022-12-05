import os
import tempfile

import pytest

from ofrak.core.architecture import ProgramAttributes
from ofrak_patch_maker.model import PatchRegionConfig
from ofrak_patch_maker.patch_maker import PatchMaker
from ofrak_patch_maker.toolchain.model import (
    CompilerOptimizationLevel,
    ToolchainConfig,
    BinFileType,
    Segment,
)
from ofrak_patch_maker.toolchain.utils import get_file_format
from ofrak_patch_maker.toolchain.version import ToolchainVersion
from ofrak_patch_maker_test import ToolchainUnderTest, CURRENT_DIRECTORY
from ofrak_patch_maker_test.toolchain_asm import (
    run_challenge_3_reloc_toy_example_test,
    run_monkey_patch_test,
)
from ofrak_patch_maker_test.toolchain_c import run_hello_world_test, run_bounds_check_test
from ofrak_type.architecture import (
    InstructionSet,
    ProcessorType,
)
from ofrak_type.bit_width import BitWidth
from ofrak_type.endianness import Endianness
from ofrak_type.memory_permissions import MemoryPermissions

M68K_EXTENSION = ".m68k"


@pytest.fixture(
    params=[
        ToolchainUnderTest(
            ToolchainVersion.GNU_M68K_LINUX_10,
            ProgramAttributes(
                InstructionSet.M68K,
                None,
                BitWidth.BIT_32,
                Endianness.BIG_ENDIAN,
                ProcessorType.COLDFIRE4E,
            ),
            M68K_EXTENSION,
        ),
        ToolchainUnderTest(
            ToolchainVersion.VBCC_M68K_0_9,
            ProgramAttributes(
                InstructionSet.M68K,
                None,
                BitWidth.BIT_32,
                Endianness.BIG_ENDIAN,
                ProcessorType.COLDFIRE4E,
            ),
            M68K_EXTENSION,
        ),
    ]
)
def toolchain_under_test(request) -> ToolchainUnderTest:
    return request.param


# ASM Tests
def test_challenge_3_reloc_toy_example(toolchain_under_test: ToolchainUnderTest):
    run_challenge_3_reloc_toy_example_test(
        toolchain_under_test.toolchain_version,
        toolchain_under_test.proc,
        toolchain_under_test.extension,
    )


def test_monkey_patch(toolchain_under_test: ToolchainUnderTest):
    run_monkey_patch_test(
        toolchain_under_test.toolchain_version,
        toolchain_under_test.proc,
        toolchain_under_test.extension,
    )


# C Tests
def test_bounds_check(toolchain_under_test: ToolchainUnderTest):
    run_bounds_check_test(toolchain_under_test.toolchain_version, toolchain_under_test.proc)


def test_hello_world(toolchain_under_test: ToolchainUnderTest):
    run_hello_world_test(
        toolchain_under_test.toolchain_version,
        toolchain_under_test.proc,
    )


def test_m68k_alignment():
    program_attributes = ProgramAttributes(
        InstructionSet.M68K,
        None,
        BitWidth.BIT_32,
        Endianness.BIG_ENDIAN,
        ProcessorType.COLDFIRE4E,
    )

    tc_config = ToolchainConfig(
        file_format=BinFileType.ELF,
        force_inlines=True,
        relocatable=False,
        no_std_lib=True,
        no_jump_tables=True,
        no_bss_section=True,
        create_map_files=True,
        compiler_optimization_level=CompilerOptimizationLevel.NONE,
        debug_info=True,
        check_overlap=False,
        hard_float=True,
    )

    build_dir = tempfile.mkdtemp()

    patch_maker = PatchMaker(
        program_attributes=program_attributes,
        toolchain_config=tc_config,
        toolchain_version=ToolchainVersion.GNU_M68K_LINUX_10,
        build_dir=build_dir,
        base_symbols={"bye_world": 0x80000468},
    )
    patch_source = os.path.join(CURRENT_DIRECTORY, "test_alignment/patch_m68k.as")
    patch_bom = patch_maker.make_bom("patch", [patch_source], [], [])

    # Grab the resulting object paths and re-map them to the segments we chose for each source file.
    patch_object = patch_bom.object_map[patch_source]
    text_segment_patch = Segment(
        segment_name=".text",
        vm_address=0x80000456,
        offset=0,
        is_entry=False,
        length=2,
        access_perms=MemoryPermissions.RX,
    )
    segment_dict = {
        patch_object.path: (text_segment_patch,),
    }

    exec_path = os.path.join(build_dir, "patch_exec")
    # Generate a PatchRegionConfig from your segment Dict.
    # This data structure informs ld script generation which regions to create for every segment.
    p = PatchRegionConfig(patch_bom.name + "_patch", segment_dict)
    fem = patch_maker.make_fem([(patch_bom, p)], exec_path)

    assert os.path.exists(exec_path)
    assert get_file_format(exec_path) == tc_config.file_format
    code_segments = [s for s in fem.executable.segments if s.access_perms == MemoryPermissions.RX]
    assert len(code_segments) == 1
    assert code_segments[0].vm_address == 0x80000456
    assert code_segments[0].length == 2
    with open(exec_path, "rb") as f:
        dat = f.read()
        code_offset = code_segments[0].offset
        assert dat[code_offset : code_offset + 2] == b"\x60\x10"
