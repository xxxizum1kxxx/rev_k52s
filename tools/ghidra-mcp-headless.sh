#!/bin/bash
# Start the GhidraMCP headless server on 127.0.0.1:8089 with the K5IIs project open.
# Do not run while the same project is open in the Ghidra GUI (project lock).
set -e
GHIDRA_HOME=${GHIDRA_HOME:-$HOME/tools/ghidra_12.1.4_PUBLIC}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

CP="$GHIDRA_HOME/Ghidra/Extensions/GhidraMCP/lib/GhidraMCP-7.0.0.jar"
for jar in "$GHIDRA_HOME"/Ghidra/{Framework,Features,Debug,Processors}/*/lib/*.jar \
           "$GHIDRA_HOME"/Ghidra/Extensions/ghidra-fr60/lib/*.jar; do
    CP="$CP:$jar"
done

exec java -Xmx${GHIDRA_MCP_XMX:-8g} -XX:+UseG1GC \
    -Dghidra.home="$GHIDRA_HOME" -Dapplication.name=GhidraMCP \
    -classpath "$CP" com.xebyte.headless.GhidraMCPHeadlessServer \
    --bind 127.0.0.1 --port 8089 \
    --project "$ROOT/ghidra" --program fwdc218b_dec.bin "$@"
