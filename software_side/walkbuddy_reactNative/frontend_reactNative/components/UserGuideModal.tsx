import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

interface UserGuideModalProps {
  visible: boolean;
  onClose: () => void;
  showAsFirstTime?: boolean;
}

export default function UserGuideModal({
  visible,
  onClose,
  showAsFirstTime = false,
}: UserGuideModalProps) {
  const colors = useThemeColors();
  const [activeTab, setActiveTab] = useState<"guide" | "faq">("guide");

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={[styles.container, { backgroundColor: colors.surface }]}>
          {/* Header */}
          <View style={[styles.header, { borderBottomColor: colors.border }]}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              {showAsFirstTime ? "Welcome to Audiobooks!" : "User Guide & FAQs"}
            </Text>
            <Pressable
              onPress={onClose}
              style={styles.closeButton}
              accessibilityLabel="Close guide"
            >
              <Ionicons name="close" size={24} color={colors.text} />
            </Pressable>
          </View>

          {/* Tabs */}
          <View style={[styles.tabContainer, { borderBottomColor: colors.border }]}>
            <Pressable
              onPress={() => setActiveTab("guide")}
              style={[styles.tab, activeTab === "guide" && { borderBottomColor: colors.accent }]}
            >
              <Text
                style={[
                  styles.tabText,
                  { color: colors.textMuted },
                  activeTab === "guide" && { color: colors.accent, fontWeight: "600" },
                ]}
              >
                User Guide
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setActiveTab("faq")}
              style={[styles.tab, activeTab === "faq" && { borderBottomColor: colors.accent }]}
            >
              <Text
                style={[
                  styles.tabText,
                  { color: colors.textMuted },
                  activeTab === "faq" && { color: colors.accent, fontWeight: "600" },
                ]}
              >
                FAQs
              </Text>
            </Pressable>
          </View>

          {/* Content */}
          <ScrollView style={styles.content} showsVerticalScrollIndicator={true}>
            {activeTab === "guide" ? <UserGuideContent /> : <FAQContent />}
          </ScrollView>

          {/* Footer for first-time users */}
          {showAsFirstTime && (
            <View style={[styles.footer, { borderTopColor: colors.border }]}>
              <Pressable
                onPress={onClose}
                style={[styles.getStartedButton, { backgroundColor: colors.accent }]}
                accessibilityLabel="Get started"
              >
                <Text style={[styles.getStartedText, { color: colors.accentText }]}>Get Started</Text>
              </Pressable>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
}

function UserGuideContent() {
  return (
    <View style={styles.guideContent}>
      <Section
        icon="search"
        title="Searching for Audiobooks"
        content={[
          "• Type at least 3 characters in the search bar to find audiobooks",
          "• Use the microphone button (🎤) to search by voice",
          "• Click 'Search Audiobooks' button to execute your search",
          "• Browse popular audiobooks when the search bar is empty",
        ]}
      />

      <Section
        icon="filter"
        title="Using Filters"
        content={[
          "• Language: Filter by the language of the audiobook",
          "• Genre: Choose from fiction, non-fiction, science fiction, etc.",
          "• Duration: Filter by length (<1h, 1-3h, 3-10h, 10h+)",
          "• Sort: Sort by relevance, popularity, newest, longest, or alphabetically",
          "• You can combine multiple filters for precise results",
          "• Click 'Clear filters' to remove all active filters",
        ]}
      />

      <Section
        icon="mic"
        title="Voice Search"
        content={[
          "• Click the microphone icon in the search bar",
          "• Speak clearly the book title, author, or topic",
          "• The recognized text will appear in the search bar automatically",
          "• Click the microphone again to stop listening",
          "• Works best in Chrome or Edge browsers",
        ]}
      />

      <Section
        icon="play-circle"
        title="Playing Audiobooks"
        content={[
          "• Tap on any audiobook card to open the player",
          "• Use play/pause controls to manage playback",
          "• Adjust playback speed in the player settings",
          "• Your progress is automatically saved",
        ]}
      />

      <Section
        icon="heart"
        title="Favorites & Listen Later"
        content={[
          "• Tap the heart icon to add books to favorites",
          "• Tap the bookmark icon to add to 'Listen Later'",
          "• Access favorites and listen later from the menu (⋮)",
          "• Your saved books persist across sessions",
        ]}
      />

      <Section
        icon="time"
        title="Search History"
        content={[
          "• Your recent searches are saved automatically",
          "• Access history from the menu (⋮)",
          "• Quickly return to previously searched books",
        ]}
      />

      <Section
        icon="information-circle"
        title="Tips & Best Practices"
        content={[
          "• Use specific book titles or author names for best results",
          "• Combine filters with search terms for precise discovery",
          "• Popular audiobooks are shown when you first open the app",
          "• All audiobooks are from LibriVox (public domain)",
          "• Books are free to listen to without any restrictions",
        ]}
      />
    </View>
  );
}

function FAQContent() {
  const colors = useThemeColors();
  const faqs = [
    {
      question: "How do I search for audiobooks?",
      answer:
        "Type at least 3 characters in the search bar, or use the microphone button to search by voice. You can also use filters to narrow down your search by language, genre, duration, and more.",
    },
    {
      question: "Can I use voice search?",
      answer:
        "Yes! Click the microphone icon in the search bar and speak your search query. Voice search works best in Chrome or Edge browsers. Make sure to allow microphone permissions when prompted.",
    },
    {
      question: "How do filters work?",
      answer:
        "Filters help you find audiobooks that match specific criteria. You can filter by language, genre, duration, and sort options. Multiple filters can be combined. Click any filter chip to open the selection menu.",
    },
    {
      question: "Are the audiobooks free?",
      answer:
        "Yes! All audiobooks are from LibriVox, which provides free public domain audiobooks. There are no costs or subscriptions required.",
    },
    {
      question: "Can I save audiobooks for later?",
      answer:
        "Yes! You can add books to favorites (heart icon) or to your 'Listen Later' list (bookmark icon). Access these from the menu (three dots) in the top right corner.",
    },
    {
      question: "How do I play an audiobook?",
      answer:
        "Simply tap on any audiobook card to open the player screen. Use the play/pause controls to manage playback. Your progress is automatically saved.",
    },
    {
      question: "Can I change playback speed?",
      answer:
        "Yes! Playback speed controls are available in the audiobook player screen. You can adjust the speed to your preference.",
    },
    {
      question: "What languages are available?",
      answer:
        "Audiobooks are available in many languages. Use the Language filter to see all available languages. English is the most common, but there are books in over 100 languages.",
    },
    {
      question: "How do I clear my search history?",
      answer:
        "Your search history is saved automatically. You can access it from the menu (three dots). Currently, history persists to help you quickly return to previous searches.",
    },
    {
      question: "Why can't I find a specific book?",
      answer:
        "LibriVox contains public domain books, so newer copyrighted books may not be available. Try searching with different keywords, or use filters to browse available books in your preferred genre or language.",
    },
    {
      question: "Do I need an internet connection?",
      answer:
        "Yes, you need an internet connection to search and stream audiobooks. The app streams audio from LibriVox servers.",
    },
    {
      question: "Can I download audiobooks for offline listening?",
      answer:
        "Currently, audiobooks are streamed online. Offline downloading is not available, but you can bookmark books for easy access later.",
    },
  ];

  return (
    <View style={styles.faqContent}>
      {faqs.map((faq, index) => (
        <View key={index} style={[styles.faqItem, { borderBottomColor: colors.border }]}>
          <View style={styles.faqQuestion}>
            <Ionicons name="help-circle" size={20} color={colors.accent} />
            <Text style={[styles.faqQuestionText, { color: colors.text }]}>{faq.question}</Text>
          </View>
          <Text style={[styles.faqAnswer, { color: colors.textMuted }]}>{faq.answer}</Text>
        </View>
      ))}
    </View>
  );
}

function Section({
  icon,
  title,
  content,
}: {
  icon: string;
  title: string;
  content: string[];
}) {
  const colors = useThemeColors();
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name={icon as any} size={24} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>{title}</Text>
      </View>
      {content.map((item, index) => (
        <Text key={index} style={[styles.sectionItem, { color: colors.textMuted }]}>
          {item}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    justifyContent: "flex-end",
  },
  container: {
    borderTopLeftRadius: Radius.xl - 2,
    borderTopRightRadius: Radius.xl - 2,
    maxHeight: "90%",
    minHeight: "70%",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: Spacing.xxl - 4,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: Typography.size.lg,
    fontWeight: "bold",
    flex: 1,
  },
  closeButton: {
    padding: Spacing.xs,
  },
  tabContainer: {
    flexDirection: "row",
    borderBottomWidth: 1,
  },
  tab: {
    flex: 1,
    paddingVertical: Spacing.lg,
    alignItems: "center",
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabText: {
    fontSize: Typography.size.base,
  },
  content: {
    flex: 1,
    padding: Spacing.xxl - 4,
  },
  guideContent: {
    gap: Spacing.xxl,
  },
  section: {
    marginBottom: Spacing.sm,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: Typography.size.md,
    fontWeight: "600",
  },
  sectionItem: {
    fontSize: Typography.size.sm,
    lineHeight: 22,
    marginBottom: Spacing.sm,
    marginLeft: 36,
  },
  faqContent: {
    gap: Spacing.xl,
  },
  faqItem: {
    marginBottom: Spacing.lg,
    paddingBottom: Spacing.lg,
    borderBottomWidth: 1,
  },
  faqQuestion: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm + 2,
    marginBottom: Spacing.sm,
  },
  faqQuestionText: {
    flex: 1,
    fontSize: Typography.size.base,
    fontWeight: "600",
    lineHeight: 22,
  },
  faqAnswer: {
    fontSize: Typography.size.sm,
    lineHeight: 20,
    marginLeft: 30,
  },
  footer: {
    padding: Spacing.xxl - 4,
    borderTopWidth: 1,
  },
  getStartedButton: {
    paddingVertical: Spacing.md + 2,
    paddingHorizontal: Spacing.xxl + 8,
    borderRadius: 25,
    alignItems: "center",
  },
  getStartedText: {
    fontSize: Typography.size.base,
    fontWeight: "600",
  },
});
