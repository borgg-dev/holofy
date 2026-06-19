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
      // Reanimated v4 moved its worklet babel transform into react-native-worklets; it must
      // remain the LAST plugin in the list.
      "react-native-worklets/plugin",
    ],
  };
};
