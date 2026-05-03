import html


class BotUITexts:
    @staticmethod
    def usage_instructions(lang: str, t, icon, lang_kh: str) -> str:
        if lang == lang_kh:
            return (
                f"<b>របៀបប្រើប្រាស់កម្មវិធី</b>\n"
                f"\n"
                f"<b>I. {icon('add')} បញ្ចូលចំណាយ/ចំណូល</b>\n"
                f"• ចុច <b>{icon('add')} បន្ថែមចំណាយ</b> ឬ <b>{icon('add')} បន្ថែមចំណូល</b>\n"
                f"• ឬសរសេរ៖ <code>ចំណាយ $5 អាហារ</code> ឬ <code>ចំណូល $100 ប្រាក់ខែ</code>\n"
                f"\n"
                f"<b>II. {icon('balance')} មើលសមតុល្យ និងរបាយការណ៍</b>\n"
                f"• ចុច <b>{icon('balance')} សមតុល្យ</b> ដើម្បីមើលសមតុល្យ\n"
                f"• ចុច <b>{icon('summary')} សរុប</b> ឬ <b>{icon('month')} ខែនេះ</b> ដើម្បីមើលរបាយការណ៍\n"
                f"• ឬសរសេរ៖ <code>សមតុល្យ</code> ឬ <code>របាយការណ៍</code>\n"
                f"\n"
                f"<b>III. {icon('lang_kh')} ប្តូរភាសា</b>\n"
                f"• ចុច <b>{icon('lang_kh')} Khmer</b> ឬ <b>{icon('lang_en')} English</b> ដើម្បីប្ដូរភាសា\n"
                f"\n"
                f"<b>IV. 🛠️ បង្ហាញ/បិទប៊ូតុង</b>\n"
                f"• ចុច <b>Show All Buttons</b> ដើម្បីបង្ហាញប៊ូតុងទាំងអស់\n"
                f"• ចុច <b>Hide All Buttons</b> ដើម្បីបិទប៊ូតុង\n"
                f"\n"
                f"<b>V. {icon('back')} ត្រឡប់ក្រោយ</b>\n"
                f"• ចុច <b>⬅️ ត្រឡប់ក្រោយ</b> ដើម្បីត្រឡប់ទៅមុខងារមុន\n"
                f"\n"
                f"<b>VI. {icon('tip')} គន្លឹះបន្ថែម</b>\n"
                f"• អាចផ្ញើសារជាភាសាធម្មតា ឬប្រើប៊ូតុងសម្រាប់សកម្មភាពលឿន\n"
                f"• អាចបញ្ចូលសំឡេង ឬរូបភាព (AI នឹងជួយយល់)\n"
                f"\n"
                f"<i>មានសំណួរឬបញ្ហា? ចុច Help ឬទាក់ទង admin!</i>"
            )
        return (
            f"<b>How to Use the App</b>\n"
            f"\n"
            f"<b>I. {icon('add')} Add Expense/Income</b>\n"
            f"• Tap <b>{icon('add')} Add Expense</b> or <b>{icon('add')} Add Income</b>\n"
            f"• Or type: <code>spent $5 on food</code> or <code>earned $100 salary</code>\n"
            f"\n"
            f"<b>II. {icon('balance')} View Balance & Reports</b>\n"
            f"• Tap <b>{icon('balance')} Balance</b> to see your balance\n"
            f"• Tap <b>{icon('summary')} Summary</b> or <b>{icon('month')} This Month</b> for reports\n"
            f"• Or type: <code>balance</code> or <code>report</code>\n"
            f"\n"
            f"<b>III. {icon('lang_kh')} Change Language</b>\n"
            f"• Tap <b>{icon('lang_kh')} Khmer</b> or <b>{icon('lang_en')} English</b> to switch language\n"
            f"\n"
            f"<b>IV. 🛠️ Show/Hide Buttons</b>\n"
            f"• Tap <b>Show All Buttons</b> to show all quick actions\n"
            f"• Tap <b>Hide All Buttons</b> to hide them\n"
            f"\n"
            f"<b>V. {icon('back')} Back</b>\n"
            f"• Tap <b>⬅️ Back</b> to return to the previous menu\n"
            f"\n"
            f"<b>VI. {icon('tip')} Tips</b>\n"
            f"• You can type naturally or use the buttons for quick actions\n"
            f"• You can send voice or photo (AI will help understand)\n"
            f"\n"
            f"<i>Need help? Tap Help or contact admin!</i>"
        )

    @staticmethod
    def formatting_showcase(lang: str, icon, lang_kh: str) -> str:
        if lang == lang_kh:
            return (
                f"<b>{icon('style')} រចនាប័ទ្មអត្ថបទ</b>\n"
                "• <b>ដិត (Bold)</b>\n"
                "• <i>ទ្រេត (Italic)</i>\n"
                "• <blockquote>Quote: ឧទាហរណ៍សម្រង់អត្ថបទ</blockquote>\n"
                "• <tg-spoiler>Tip សម្ងាត់: ចុចលើ spoiler ដើម្បីបង្ហាញ</tg-spoiler>\n"
            )

        return (
            f"<b>{icon('style')} Text Formatting</b>\n"
            "• <b>Bold</b>\n"
            "• <i>Italic</i>\n"
            "• <blockquote>Quote: sample highlighted note</blockquote>\n"
            "• <tg-spoiler>Hidden tip: tap spoiler to reveal</tg-spoiler>\n"
        )

    @staticmethod
    def start_help_text(lang: str, user_name: str, user_id: int, app_url: str, lang_kh: str) -> str:
        safe_name = html.escape(user_name)
        if lang == lang_kh:
            return (
                f"<b>សួស្តី {safe_name}</b>\n\n"
                f"<b>អត្ថប្រយោជន៍សំខាន់ៗ</b>\n"
                f"• កត់ត្រាចំណូល/ចំណាយបានលឿន\n"
                f"• មើលសមតុល្យ និងរបាយការណ៍បានភ្លាមៗ\n"
                f"• AI ជួយចាត់ថ្នាក់ចំណាយដោយស្វ័យប្រវត្តិ\n"
                f"• ព្យាករណ៍ការចំណាយ និងផ្តល់អនុសាសន៍សន្សំប្រាក់\n"
                f"• ផ្តល់របាយការណ៍ និងសេចក្តីសង្ខេបប្រចាំខែជាភាសាខ្មែរ និងអង់គ្លេស\n"
                f"• មានសុវត្ថិភាពខ្ពស់ ដោយប្រើការអ៊ិនគ្រីបទិន្នន័យ\n\n"
                f"<b>របៀបប្រើប្រាស់</b>\n"
                f"• ផ្ញើសារចំណាយ ឬ ចំណូលដោយភាសាធម្មតា\n"
                f"• អាចសួរអំពីសមតុល្យ ឬរបាយការណ៍ប្រចាំខែ\n\n"
                f"អាចសរសេរ និយាយ ឬបញ្ចូលរូបភាព ឯកសារ (upload) បាន។\n"
                f"Tip: ចុចប៊ូតុងខាងក្រោម ដើម្បីប្រើបានលឿន។"
            )

        return (
            f"<b>Hello {safe_name}</b>\n\n"
            f"<b>Key Benefits</b>\n"
            f"• Quickly record income/expenses\n"
            f"• Instantly view balance and reports\n"
            f"• AI auto-categorizes your spending\n"
            f"• Predicts expenses & gives saving tips\n"
            f"• Monthly reports and summaries in Khmer & English\n"
            f"• High security with encrypted data\n\n"
            f"<b>How to use</b>\n"
            f"• Send income/expense in natural language\n"
            f"• Ask for balance or monthly report\n\n"
            f"You can type, speak, or upload images/docs.\n"
            f"Tip: Tap the buttons below for faster actions."
        )
