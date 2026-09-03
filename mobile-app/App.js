import React, { useState } from "react";
import {
  Alert,
  Linking,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { LINKS } from "./src/links";

const COLORS = {
  background: "#090510",
  panel: "#17102A",
  panelSoft: "#211735",
  text: "#FFFFFF",
  muted: "#B9AEC9",
  pink: "#EF3D98",
  purple: "#9B4DCC",
  teal: "#50D6D0",
  gold: "#FFC867",
  line: "rgba(255,255,255,0.13)"
};

const TABS = [
  { key: "home", label: "Home", icon: "★" },
  { key: "family", label: "Family", icon: "♥" },
  { key: "staff", label: "Staff", icon: "✓" },
  { key: "more", label: "More", icon: "•••" }
];

async function openLink(url) {
  try {
    const supported = await Linking.canOpenURL(url);
    if (!supported) {
      Alert.alert("Link unavailable", "This link could not be opened on this device.");
      return;
    }
    await Linking.openURL(url);
  } catch (error) {
    Alert.alert("Could not open link", "Please try again.");
  }
}

function ActionCard({ icon, title, description, url, accent = COLORS.pink }) {
  return (
    <TouchableOpacity
      activeOpacity={0.82}
      onPress={() => openLink(url)}
      style={[styles.actionCard, { borderColor: accent + "55" }]}
    >
      <View style={[styles.iconBox, { backgroundColor: accent + "20" }]}>
        <Text style={[styles.cardIcon, { color: accent }]}>{icon}</Text>
      </View>
      <View style={styles.cardCopy}>
        <Text style={styles.cardTitle}>{title}</Text>
        <Text style={styles.cardDescription}>{description}</Text>
      </View>
      <Text style={[styles.chevron, { color: accent }]}>›</Text>
    </TouchableOpacity>
  );
}

function SectionTitle({ children, subtitle }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.sectionTitle}>{children}</Text>
      {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
    </View>
  );
}

function HomeScreen({ setTab }) {
  return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.hero}>
        <Text style={styles.eyebrow}>STAGE STARZ ACADEMY OF DANCE</Text>
        <Text style={styles.heroTitle}>Everything Stage Starz, in one place.</Text>
        <Text style={styles.heroText}>
          Quick access for families, teachers, staff and management.
        </Text>
      </View>

      <SectionTitle subtitle="Choose the area you need.">Your Stage Starz app</SectionTitle>

      <View style={styles.choiceRow}>
        <TouchableOpacity
          style={[styles.choiceCard, { borderColor: COLORS.pink + "66" }]}
          activeOpacity={0.82}
          onPress={() => setTab("family")}
        >
          <Text style={styles.choiceIcon}>♥</Text>
          <Text style={styles.choiceTitle}>Families</Text>
          <Text style={styles.choiceText}>Payments, schedules, registration and parent resources.</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.choiceCard, { borderColor: COLORS.teal + "66" }]}
          activeOpacity={0.82}
          onPress={() => setTab("staff")}
        >
          <Text style={[styles.choiceIcon, { color: COLORS.teal }]}>✓</Text>
          <Text style={styles.choiceTitle}>Staff</Text>
          <Text style={styles.choiceText}>Classes, rosters, attendance, time clock and management.</Text>
        </TouchableOpacity>
      </View>

      <SectionTitle subtitle="Most-used studio links.">Quick access</SectionTitle>

      <ActionCard
        icon="⌕"
        title="Find a Class"
        description="Explore current Stage Starz class options."
        url={LINKS.classFinder}
        accent={COLORS.purple}
      />
      <ActionCard
        icon="★"
        title="Recital Information"
        description="Recital details, venue information and updates."
        url={LINKS.recital}
        accent={COLORS.gold}
      />
      <ActionCard
        icon="🛍"
        title="Stage Starz Shop"
        description="Open the Stage Starz online store."
        url={LINKS.shop}
        accent={COLORS.pink}
      />

      <View style={styles.notice}>
        <Text style={styles.noticeTitle}>Version 1</Text>
        <Text style={styles.noticeText}>
          Jackrabbit and Stage Starz management tools open their secure web login pages.
          Your existing usernames and passwords continue to work.
        </Text>
      </View>
    </ScrollView>
  );
}

function FamilyScreen() {
  return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.screenIntro}>
        <Text style={styles.eyebrow}>FAMILY AREA</Text>
        <Text style={styles.screenTitle}>Parent & dancer resources</Text>
        <Text style={styles.screenText}>
          Use Jackrabbit for account information, schedules, payments and registration.
        </Text>
      </View>

      <ActionCard
        icon="$"
        title="Jackrabbit Parent Portal"
        description="Make payments, view your dancer's schedule and manage your family account."
        url={LINKS.parentPortal}
        accent={COLORS.pink}
      />
      <ActionCard
        icon="⌕"
        title="Class Finder"
        description="Find the right Stage Starz class."
        url={LINKS.classFinder}
        accent={COLORS.purple}
      />
      <ActionCard
        icon="★"
        title="Recital"
        description="Recital information and important updates."
        url={LINKS.recital}
        accent={COLORS.gold}
      />
      <ActionCard
        icon="♛"
        title="Competition"
        description="Competition programs and team information."
        url={LINKS.competition}
        accent={COLORS.teal}
      />
      <ActionCard
        icon="⌂"
        title="Parent Hub"
        description="Stage Starz parent resources in one place."
        url={LINKS.parentHub}
        accent={COLORS.pink}
      />
      <ActionCard
        icon="🛍"
        title="Shop"
        description="Spirit wear and Stage Starz merchandise."
        url={LINKS.shop}
        accent={COLORS.purple}
      />
    </ScrollView>
  );
}

function StaffScreen() {
  return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.screenIntro}>
        <Text style={[styles.eyebrow, { color: COLORS.teal }]}>TEACHER & STAFF AREA</Text>
        <Text style={styles.screenTitle}>Classes, attendance & management</Text>
        <Text style={styles.screenText}>
          Staff tools remain protected by the Jackrabbit and Stage Starz login screens.
        </Text>
      </View>

      <ActionCard
        icon="✓"
        title="Teacher & Staff Portal"
        description="Classes, rosters, attendance and time clock in Jackrabbit."
        url={LINKS.staffPortal}
        accent={COLORS.teal}
      />
      <ActionCard
        icon="⚙"
        title="Stage Starz Management"
        description="Open the secure Stage Starz management center."
        url={LINKS.management}
        accent={COLORS.purple}
      />
      <ActionCard
        icon="▥"
        title="Website Traffic"
        description="View today's traffic plus 7, 30 and 90-day reports."
        url={LINKS.traffic}
        accent={COLORS.gold}
      />
      <ActionCard
        icon="↗"
        title="Open Public Website"
        description="View the live Stage Starz website."
        url={LINKS.website}
        accent={COLORS.pink}
      />

      <View style={styles.notice}>
        <Text style={styles.noticeTitle}>Staff security</Text>
        <Text style={styles.noticeText}>
          Version 1 does not store staff passwords inside the app. Authentication stays with
          Jackrabbit and the Stage Starz management system.
        </Text>
      </View>
    </ScrollView>
  );
}

function MoreScreen() {
  return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.screenIntro}>
        <Text style={styles.eyebrow}>STAGE STARZ</Text>
        <Text style={styles.screenTitle}>Contact & helpful links</Text>
        <Text style={styles.screenText}>6800 Lewis Ave, Temperance, MI 48182</Text>
      </View>

      <ActionCard
        icon="☎"
        title="Call Stage Starz"
        description="(734) 497-3740"
        url={LINKS.call}
        accent={COLORS.teal}
      />
      <ActionCard
        icon="✉"
        title="Email Stage Starz"
        description="Send an email to the studio."
        url={LINKS.email}
        accent={COLORS.purple}
      />
      <ActionCard
        icon="⌖"
        title="Get Directions"
        description="Open directions to the studio."
        url={LINKS.directions}
        accent={COLORS.gold}
      />
      <ActionCard
        icon="★"
        title="Leave a Google Review"
        description="Share your Stage Starz experience."
        url={LINKS.review}
        accent={COLORS.pink}
      />
      <ActionCard
        icon="↗"
        title="Stage Starz Website"
        description="www.stagestarzdance.com"
        url={LINKS.website}
        accent={COLORS.teal}
      />

      <Text style={styles.version}>Stage Starz Mobile · Version 1.0</Text>
    </ScrollView>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("home");

  let screen = <HomeScreen setTab={setActiveTab} />;
  if (activeTab === "family") screen = <FamilyScreen />;
  if (activeTab === "staff") screen = <StaffScreen />;
  if (activeTab === "more") screen = <MoreScreen />;

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safeArea} edges={["top", "right", "bottom", "left"]}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.background} translucent={false} />
      <View style={styles.app}>
        <View style={styles.topBar}>
          <View>
            <Text style={styles.brandSmall}>STAGE STARZ</Text>
            <Text style={styles.brand}>Academy of Dance</Text>
          </View>
          <View style={styles.starBadge}>
            <Text style={styles.starBadgeText}>★</Text>
          </View>
        </View>

        <View style={styles.body}>{screen}</View>

        <View style={styles.tabBar}>
          {TABS.map((tab) => {
            const selected = activeTab === tab.key;
            return (
              <TouchableOpacity
                key={tab.key}
                style={styles.tabButton}
                activeOpacity={0.75}
                onPress={() => setActiveTab(tab.key)}
              >
                <Text style={[styles.tabIcon, selected && styles.tabIconActive]}>{tab.icon}</Text>
                <Text style={[styles.tabLabel, selected && styles.tabLabelActive]}>{tab.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.background
  },
  app: {
    flex: 1,
    backgroundColor: COLORS.background
  },
  topBar: {
    minHeight: 68,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.line,
    backgroundColor: "#0E0817",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  brandSmall: {
    color: COLORS.pink,
    fontSize: 11,
    letterSpacing: 2.1,
    fontWeight: "900"
  },
  brand: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: "900",
    marginTop: 1
  },
  starBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: COLORS.pink + "22",
    borderWidth: 1,
    borderColor: COLORS.pink + "66"
  },
  starBadgeText: {
    color: COLORS.pink,
    fontSize: 19
  },
  body: {
    flex: 1
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 28
  },
  hero: {
    padding: 22,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: COLORS.pink + "4D",
    backgroundColor: COLORS.panel,
    marginBottom: 26
  },
  eyebrow: {
    color: COLORS.pink,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.6,
    marginBottom: 8
  },
  heroTitle: {
    color: COLORS.text,
    fontSize: 30,
    lineHeight: 35,
    fontWeight: "900"
  },
  heroText: {
    color: COLORS.muted,
    fontSize: 15,
    lineHeight: 22,
    marginTop: 11
  },
  sectionHeading: {
    marginBottom: 11,
    marginTop: 4
  },
  sectionTitle: {
    color: COLORS.text,
    fontSize: 19,
    fontWeight: "900"
  },
  sectionSubtitle: {
    color: COLORS.muted,
    fontSize: 13,
    marginTop: 3
  },
  choiceRow: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 25
  },
  choiceCard: {
    flex: 1,
    minHeight: 162,
    padding: 16,
    borderWidth: 1,
    borderRadius: 19,
    backgroundColor: COLORS.panel
  },
  choiceIcon: {
    color: COLORS.pink,
    fontSize: 25,
    fontWeight: "900",
    marginBottom: 16
  },
  choiceTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: "900"
  },
  choiceText: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6
  },
  actionCard: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    borderRadius: 18,
    borderWidth: 1,
    backgroundColor: COLORS.panel,
    marginBottom: 10
  },
  iconBox: {
    width: 48,
    height: 48,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12
  },
  cardIcon: {
    fontSize: 21,
    fontWeight: "900"
  },
  cardCopy: {
    flex: 1
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 15,
    fontWeight: "900"
  },
  cardDescription: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4
  },
  chevron: {
    fontSize: 30,
    paddingLeft: 8,
    fontWeight: "300"
  },
  notice: {
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.gold + "44",
    backgroundColor: COLORS.gold + "10"
  },
  noticeTitle: {
    color: COLORS.gold,
    fontSize: 13,
    fontWeight: "900",
    marginBottom: 5
  },
  noticeText: {
    color: "#E5D5B3",
    fontSize: 12,
    lineHeight: 18
  },
  screenIntro: {
    paddingVertical: 10,
    marginBottom: 14
  },
  screenTitle: {
    color: COLORS.text,
    fontSize: 27,
    lineHeight: 32,
    fontWeight: "900"
  },
  screenText: {
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 8
  },
  version: {
    color: COLORS.muted,
    fontSize: 11,
    textAlign: "center",
    marginTop: 20
  },
  tabBar: {
    minHeight: 68,
    flexDirection: "row",
    backgroundColor: "#0E0817",
    borderTopWidth: 1,
    borderTopColor: COLORS.line,
    paddingBottom: 4
  },
  tabButton: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  tabIcon: {
    color: COLORS.muted,
    fontSize: 17,
    fontWeight: "900"
  },
  tabIconActive: {
    color: COLORS.pink
  },
  tabLabel: {
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: "800",
    marginTop: 3
  },
  tabLabelActive: {
    color: COLORS.text
  }
});
