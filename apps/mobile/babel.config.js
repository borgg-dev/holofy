module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: [
      // Resolve "@/..." imports to ./src for clean module paths.
      [
        "module-resolver",
        {
          alias: { "@": "./src" },
          extensions: [".ts", ".tsx", ".js", ".jsx", ".json"],
        },
      ],
      // Reanimated's plugin must be listed last.
      "react-native-reanimated/plugin",
    ],
  };
};
