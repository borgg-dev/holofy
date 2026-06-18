import { useEffect } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";

import { useReduceMotion, useTheme } from "@/theme";
import { ScanIcon, SettingsIcon, VaultIcon } from "./icons";
import { Text } from "./Text";

type IconFn = (props: { size?: number; color: string }) => JSX.Element;

// The three tabs, in order. Labels live here (not the route options) so the bar owns its
// own typography and the routes stay headerless.
const TABS: { name: string; label: string; Icon: IconFn }[] = [
  { name: "index", label: "Vault", Icon: VaultIcon },
  { name: "scan", label: "Scan", Icon: ScanIcon },
  { name: "settings", label: "Settings", Icon: SettingsIcon },
];

// The Foil Vault's bottom navigation — bespoke, never the default tab bar. A near-black
// raised bar floating over the Vault ground with a hairline top edge; the active tab's
// mark and label lift to the brand violet and a short violet pip sits beneath it. The
// pip slides between tabs (reduced-motion snaps it). Inactive marks read tertiary so the
// active one carries the eye without shouting.
export function TabBar({ state, navigation }: BottomTabBarProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  // Map the navigator's route list to our ordered TABS, dropping any route the navigator
  // doesn't actually have so the bar never renders a phantom tab.
  const items = TABS.map((tab) => {
    const index = state.routes.findIndex((r) => r.name === tab.name);
    return index === -1 ? null : { ...tab, index, key: state.routes[index]!.key };
  }).filter((t): t is NonNullable<typeof t> => t !== null);

  return (
    <View
      style={[
        styles.wrap,
        {
          paddingBottom: insets.bottom + theme.space["2"],
          backgroundColor: theme.color.bgElevated,
          borderTopColor: theme.color.border,
        },
      ]}
    >
      {items.map((tab) => {
        const focused = tab.index === state.index;
        const onPress = () => {
          const event = navigation.emit({
            type: "tabPress",
            target: tab.key,
            canPreventDefault: true,
          });
          if (!focused && !event.defaultPrevented) {
            navigation.navigate(tab.name);
          }
        };
        return (
          <Pressable
            key={tab.key}
            onPress={onPress}
            accessibilityRole="tab"
            accessibilityState={{ selected: focused }}
            accessibilityLabel={tab.label}
            style={styles.tab}
            hitSlop={6}
          >
            <TabContent
              Icon={tab.Icon}
              label={tab.label}
              focused={focused}
              active={theme.color.accent}
              inactive={theme.color.textTertiary}
            />
          </Pressable>
        );
      })}
    </View>
  );
}

function TabContent({
  Icon,
  label,
  focused,
  active,
  inactive,
}: {
  Icon: IconFn;
  label: string;
  focused: boolean;
  active: string;
  inactive: string;
}) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const lift = useSharedValue(focused ? 1 : 0);

  useEffect(() => {
    const target = focused ? 1 : 0;
    lift.value = reduceMotion
      ? target
      : withTiming(target, { duration: theme.motion.duration.fast });
  }, [focused, reduceMotion, lift, theme.motion.duration.fast]);

  const pipStyle = useAnimatedStyle(() => ({
    opacity: lift.value,
    transform: [{ scaleX: 0.6 + lift.value * 0.4 }],
  }));

  const color = focused ? active : inactive;

  return (
    <View style={[styles.content, { gap: theme.space["1"] }]}>
      <Icon size={24} color={color} />
      <Text variant="caption" style={{ color }}>
        {label}
      </Text>
      <Animated.View style={[styles.pip, { backgroundColor: active }, pipStyle]} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  tab: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { alignItems: "center", justifyContent: "center" },
  pip: {
    width: 18,
    height: 3,
    borderRadius: 2,
    marginTop: 2,
  },
});
