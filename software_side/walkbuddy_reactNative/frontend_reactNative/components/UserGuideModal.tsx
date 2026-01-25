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
  const [activeTab, setActiveTab] = useState<"guide" | "faq">("guide");

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>
              {showAsFirstTime ? "Welcome to Audiobooks!" : "User Guide & FAQs"}
            </Text>
            <Pressable
              onPress={onClose}
              style={styles.closeButton}
              accessibilityLabel="Close guide"
            >
              <Ionicons name="close" size={24} color="#FFF" />
            </Pressable>
          </View>

          {/* Tabs */}
          <View style={styles.tabContainer}>
            <Pressable
              onPress={() => setActiveTab("guide")}
              style={[styles.tab, activeTab === "guide" && styles.tabActive]}
            >
              <Text
                style={[
                  styles.tabText,
                  activeTab === "guide" && styles.tabTextActive,
                ]}
              >
                User Guide
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setActiveTab("faq")}
              style={[styles.tab, activeTab === "faq" && styles.tabActive]}
            >
              <Text
                style={[
                  styles.tabText,
                  activeTab === "faq" && styles.tabTextActive,
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
            <View style={styles.footer}>
              <Pressable
                onPress={onClose}
                style={styles.getStartedButton}
                accessibilityLabel="Get started"
              >
                <Text style={styles.getStartedText}>Get Started</Text>
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
        <View key={index} style={styles.faqItem}>
          <View style={styles.faqQuestion}>
            <Ionicons name="help-circle" size={20} color="#F9A826" />
            <Text style={styles.faqQuestionText}>{faq.question}</Text>
          </View>
          <Text style={styles.faqAnswer}>{faq.answer}</Text>
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
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name={icon as any} size={24} color="#F9A826" />
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {content.map((item, index) => (
        <Text key={index} style={styles.sectionItem}>
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
    backgroundColor: "#1B263B",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "90%",
    minHeight: "70%",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#FFF",
    flex: 1,
  },
  closeButton: {
    padding: 4,
  },
  tabContainer: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  tab: {
    flex: 1,
    paddingVertical: 16,
    alignItems: "center",
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabActive: {
    borderBottomColor: "#F9A826",
  },
  tabText: {
    fontSize: 16,
    color: "#888",
    fontWeight: "500",
  },
  tabTextActive: {
    color: "#F9A826",
    fontWeight: "600",
  },
  content: {
    flex: 1,
    padding: 20,
  },
  guideContent: {
    gap: 24,
  },
  section: {
    marginBottom: 8,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#FFF",
  },
  sectionItem: {
    fontSize: 14,
    color: "#CCC",
    lineHeight: 22,
    marginBottom: 8,
    marginLeft: 36,
  },
  faqContent: {
    gap: 20,
  },
  faqItem: {
    marginBottom: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  faqQuestion: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginBottom: 8,
  },
  faqQuestionText: {
    flex: 1,
    fontSize: 16,
    fontWeight: "600",
    color: "#FFF",
    lineHeight: 22,
  },
  faqAnswer: {
    fontSize: 14,
    color: "#CCC",
    lineHeight: 20,
    marginLeft: 30,
  },
  footer: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: "#2A2A2A",
  },
  getStartedButton: {
    backgroundColor: "#F9A826",
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 25,
    alignItems: "center",
  },
  getStartedText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "600",
  },
});
