// Disassemble and create functions at addresses listed (hex, one per line) in the file given as script arg.
// @category K5IIs
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;

public class SeedFunctions extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		Path seeds = Path.of(args.length > 0 ? args[0] : askString("Seeds", "seed file path"));
		AddressSet set = new AddressSet();
		int n = 0;
		for (String line : Files.readAllLines(seeds)) {
			line = line.trim();
			if (line.isEmpty()) {
				continue;
			}
			Address a = toAddr(Long.parseUnsignedLong(line, 16));
			if (currentProgram.getMemory().contains(a)) {
				set.add(a);
				n++;
			}
		}
		DisassembleCommand cmd = new DisassembleCommand(set, null, true);
		cmd.applyTo(currentProgram, monitor);
		int created = 0;
		for (Address a : set.getAddresses(true)) {
			monitor.checkCancelled();
			if (getFunctionAt(a) == null && getInstructionAt(a) != null && createFunction(a, null) != null) {
				created++;
			}
		}
		println("SeedFunctions: seeds=" + n + " functionsCreated=" + created);
	}
}
