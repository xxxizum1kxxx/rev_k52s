// Report analysis health (functions, instructions, bad-instruction bookmarks with opcode histogram)
// and decompile the functions referencing a few known strings. Output path is the first script arg.
// @category K5IIs
import java.io.PrintWriter;
import java.util.Map;
import java.util.TreeMap;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.BookmarkType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class ReportStats extends GhidraScript {
	private static final String[] PROBES = { "DEBUG MODE", "C:\\%08d.%03d", "%04d/%02d/%02d" };

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		try (PrintWriter out = new PrintWriter(args.length > 0 ? args[0] : "report.txt")) {
			out.println("language: " + currentProgram.getLanguageID());
			out.println("functions: " + currentProgram.getFunctionManager().getFunctionCount());
			out.println("instructions: " + currentProgram.getListing().getNumInstructions());

			Map<String, Integer> badOps = new TreeMap<>();
			Map<String, String> samples = new TreeMap<>();
			Map<String, Integer> regions = new TreeMap<>();
			int bad = 0;
			var it = currentProgram.getBookmarkManager().getBookmarksIterator(BookmarkType.ERROR);
			while (it.hasNext()) {
				Bookmark b = it.next();
				bad++;
				regions.merge(String.format("%08x", b.getAddress().getOffset() & ~0xFFFFFL), 1, Integer::sum);
				if (b.getComment().contains("Unable to resolve constructor")) {
					byte[] bytes = getBytes(b.getAddress(), 2);
					String op = String.format("%02x%02x", bytes[0] & 0xff, bytes[1] & 0xff);
					badOps.merge(op, 1, Integer::sum);
					samples.putIfAbsent(op, b.getAddress().toString());
				}
			}
			out.println("error bookmarks: " + bad);
			out.println("error bookmarks per 1MB region: " + regions);
			out.println("unresolved-opcode histogram (16-bit opcode -> count, sample address):");
			badOps.entrySet().stream().sorted((x, y) -> y.getValue() - x.getValue()).limit(40)
					.forEach(e -> out.println("  " + e.getKey() + " " + e.getValue() + " " + samples.get(e.getKey())));

			DecompInterface di = new DecompInterface();
			di.openProgram(currentProgram);
			for (String probe : PROBES) {
				Address s = find(null, (probe + "\0").getBytes("ISO-8859-1"));
				out.println("\n=== probe \"" + probe + "\" at " + s);
				if (s == null) {
					continue;
				}
				int shown = 0;
				for (Reference r : getReferencesTo(s)) {
					Function f = getFunctionContaining(r.getFromAddress());
					out.println("  ref from " + r.getFromAddress() + " in " + (f == null ? "<no function>" : f.getName()));
					if (f != null && shown++ < 1) {
						DecompileResults res = di.decompileFunction(f, 120, monitor);
						out.println(res.decompileCompleted() ? res.getDecompiledFunction().getC()
								: "  decompile failed: " + res.getErrorMessage());
					}
				}
			}
			di.dispose();
		}
	}
}
