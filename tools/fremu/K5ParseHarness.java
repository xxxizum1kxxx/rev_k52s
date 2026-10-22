import com.nikonhacker.disassembly.OutputOption;
import com.nikonhacker.disassembly.fr.FrCPUState;
import com.nikonhacker.emu.FrEmulator;
import com.nikonhacker.emu.MasterClock;
import com.nikonhacker.emu.Platform;
import com.nikonhacker.emu.memory.DebuggableMemory;
import com.nikonhacker.emu.peripherials.interruptController.fr.FrInterruptController;

import java.io.File;

/**
 * Runs the K-5 IIs ScriptMode_parse_command (0x1060F950) on nikon-firmware-tools'
 * FrEmulator, with the same calling convention as tools/emulate_parse.py:
 * R4 = object, R5 = token, R6 = 0x30-byte cmd[] (cmd[0x25] preset to 0xFF).
 *
 *   java -cp CLASSES:LIB/* K5ParseHarness fw/fwdc218b_dec.bin "DEBUG_MODE EN" ...
 */
public class K5ParseHarness {
    static final int PARSE = 0x1060F950;
    static final int TOK = 0xC0F00000, OUT = 0xC0F01000, OBJ = 0xC0F02000, STK = 0xC0F80000;
    static final int RET = 0x10ABFFF0;
    static final int CMD_LEN = 0x30;
    static final long MAX_STEPS = 2_000_000;

    public static void main(String[] args) throws Exception {
        File image = new File(args[0]);
        for (int a = 1; a < args.length; a++) {
            run(image, args[a]);
        }
    }

    static void run(File image, String token) throws Exception {
        DebuggableMemory mem = new DebuggableMemory(false);
        mem.loadFile(image, 0x10000000, false);
        mem.map(0xC0000000, 0x01000000, true, true, false);
        mem.setLogMemoryMessages(false);

        byte[] tb = (token + "\0").getBytes("ASCII");
        for (int i = 0; i < tb.length; i++) mem.store8(TOK + i, tb[i]);
        for (int i = 0; i < CMD_LEN; i++) mem.store8(OUT + i, i == 0x25 ? 0xFF : 0);

        FrCPUState cpu = new FrCPUState(PARSE);
        cpu.setReg(4, OBJ);
        cpu.setReg(5, TOK);
        cpu.setReg(6, OUT);
        cpu.setReg(FrCPUState.SP, STK);
        cpu.setReg(FrCPUState.RP, RET);
        cpu.pc = PARSE;

        Platform platform = new Platform(new MasterClock());
        platform.setCpuState(cpu);
        platform.setMemory(mem);
        FrInterruptController ic = new FrInterruptController(platform);
        platform.setInterruptController(ic);

        FrEmulator emu = new FrEmulator(platform);
        emu.setOutputOptions(OutputOption.defaultFormatOptions);
        emu.setContext(mem, cpu, ic);

        String err = "";
        long steps = 0;
        try {
            while (cpu.pc != RET && steps < MAX_STEPS) {
                emu.onClockTick();
                steps++;
            }
            if (cpu.pc != RET) err = "step limit";
        } catch (Exception e) {
            err = String.valueOf(e.getCause() != null ? e.getCause() : e);
        }

        StringBuilder slots = new StringBuilder();
        for (int i = 0; i < CMD_LEN; i++) {
            int v = mem.loadUnsigned8(OUT + i);
            if ((i == 0x25 && v != 0xFF) || (i != 0x25 && v != 0)) {
                slots.append(String.format("%02X=%02X ", i, v));
            }
        }
        System.out.printf("%s ret=%d %-34s -> %s steps=%d %s%n",
                cpu.pc == RET && err.isEmpty() ? "OK " : "ERR",
                cpu.getReg(4), "'" + token + "'",
                slots.length() == 0 ? "-" : slots.toString().trim(), steps, err);
    }
}
