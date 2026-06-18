// Metro config for the Holofy monorepo.
// The app lives in apps/mobile but consumes @holofy/design-tokens from
// ../../packages, so Metro has to watch the repo root and resolve modules
// from both the app's and the root's node_modules.
const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];
// Don't let a hoisted and a local copy of a singleton (React) both load.
config.resolver.disableHierarchicalLookup = true;

module.exports = config;
