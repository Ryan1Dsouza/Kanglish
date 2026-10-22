package org.kanglish.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import org.kanglish.app.R
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.MessageStatus
import org.kanglish.app.databinding.ItemMessageBinding

class MessageAdapter(
    private val onTranslateClicked: (ChatMessage, Int) -> Unit,
    private val onWrongMeaningClicked: (ChatMessage, Int) -> Unit,
    private val onTeachModelClicked: (ChatMessage, Int) -> Unit = { _, _ -> }
) : RecyclerView.Adapter<MessageAdapter.MessageViewHolder>() {

    private val items = mutableListOf<ChatMessage>()

    fun submitList(newItems: List<ChatMessage>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun updateItem(position: Int) {
        if (position in 0 until items.size) {
            notifyItemChanged(position)
        }
    }

    fun getItems(): List<ChatMessage> = items

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): MessageViewHolder {
        val binding = ItemMessageBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return MessageViewHolder(binding)
    }

    override fun onBindViewHolder(holder: MessageViewHolder, position: Int) {
        holder.bind(items[position], position)
    }

    override fun getItemCount(): Int = items.size

    inner class MessageViewHolder(private val binding: ItemMessageBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(item: ChatMessage, position: Int) {
            binding.tvSender.text = item.sender
            binding.tvTimestamp.text = item.timestamp
            binding.tvOriginalText.text = item.originalText

            // Sender badge color differentiation
            val isUser = item.sender.equals("You", ignoreCase = true) || item.sender.equals("Me", ignoreCase = true)
            binding.tvSender.setTextColor(
                ContextCompat.getColor(
                    binding.root.context,
                    if (isUser) R.color.badge_you else R.color.badge_sender
                )
            )

            binding.tvGlossaryHints.visibility = View.GONE

            // Translation status & text
            when (item.status) {
                MessageStatus.PENDING -> {
                    binding.tvTranslatedText.text = "Tap Translate to generate English meaning"
                    binding.tvTranslatedText.setTextColor(ContextCompat.getColor(binding.root.context, R.color.text_muted))
                    binding.pbTranslating.visibility = View.GONE
                    binding.btnTranslateItem.text = "Translate"
                    binding.btnTranslateItem.isEnabled = true
                }
                MessageStatus.TRANSLATING -> {
                    binding.tvTranslatedText.text = "Translating with on-device model..."
                    binding.tvTranslatedText.setTextColor(ContextCompat.getColor(binding.root.context, R.color.primary_light))
                    binding.pbTranslating.visibility = View.VISIBLE
                    binding.btnTranslateItem.text = "Translating..."
                    binding.btnTranslateItem.isEnabled = false
                }
                MessageStatus.TRANSLATED -> {
                    binding.tvTranslatedText.text = item.translatedText
                    binding.tvTranslatedText.setTextColor(ContextCompat.getColor(binding.root.context, R.color.text_primary))
                    binding.pbTranslating.visibility = View.GONE
                    binding.btnTranslateItem.text = "Re-translate"
                    binding.btnTranslateItem.isEnabled = true
                }
                MessageStatus.FAILED -> {
                    binding.tvTranslatedText.text = "Translation failed. Tap Re-translate to retry."
                    binding.tvTranslatedText.setTextColor(ContextCompat.getColor(binding.root.context, R.color.flag_wrong))
                    binding.pbTranslating.visibility = View.GONE
                    binding.btnTranslateItem.text = "Retry"
                    binding.btnTranslateItem.isEnabled = true
                }
            }

            // Teacher AI Verification Box
            if (item.isTeacherChecked) {
                binding.boxTeacherVerification.visibility = View.VISIBLE
                if (item.isTeacherUncertain) {
                    binding.tvTeacherBadge.text = "UNCERTAIN"
                    binding.tvTeacherBadge.setTextColor(ContextCompat.getColor(binding.root.context, R.color.teacher_badge))
                    binding.tvTeacherText.text = item.teacherExplanation.ifBlank { "The reviewer needs more context to determine the meaning." }
                    binding.btnTeachModel.visibility = View.GONE
                } else if (item.isTeacherMatch) {
                    binding.tvTeacherBadge.text = "🎓 CLOUD REVIEW"
                    binding.tvTeacherBadge.setTextColor(ContextCompat.getColor(binding.root.context, R.color.teacher_learn))
                    binding.tvTeacherText.text = "The reviewer agrees with this translation."
                    binding.btnTeachModel.visibility = View.GONE
                } else {
                    binding.tvTeacherBadge.text = "💡 TEACHER AI SUGGESTION"
                    binding.tvTeacherBadge.setTextColor(ContextCompat.getColor(binding.root.context, R.color.teacher_badge))
                    binding.tvTeacherText.text = item.teacherSuggestion
                    binding.btnTeachModel.visibility = View.VISIBLE
                    if (item.isLearned) {
                        binding.btnTeachModel.text = "✓ Learned"
                        binding.btnTeachModel.isEnabled = false
                    } else {
                        binding.btnTeachModel.text = "Save meaning"
                        binding.btnTeachModel.isEnabled = true
                        binding.btnTeachModel.setOnClickListener {
                            onTeachModelClicked(item, position)
                        }
                    }
                }
            } else {
                binding.boxTeacherVerification.visibility = View.GONE
            }

            // User correction flag
            if (item.isFlaggedWrong && item.userCorrection.isNotBlank()) {
                binding.tvUserCorrection.text = "Flagged nuance: \"${item.userCorrection}\""
                binding.tvUserCorrection.visibility = View.VISIBLE
                binding.btnWrongMeaning.text = "Nuance Saved"
            } else {
                binding.tvUserCorrection.visibility = View.GONE
                binding.btnWrongMeaning.text = binding.root.context.getString(R.string.btn_wrong_meaning)
            }

            // Actions
            binding.btnTranslateItem.setOnClickListener {
                onTranslateClicked(item, position)
            }

            binding.btnCopyItem.setOnClickListener {
                val textToCopy = if (item.status == MessageStatus.TRANSLATED) {
                    item.translatedText
                } else {
                    item.originalText
                }
                val clipboard = binding.root.context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("Kanglish Translation", textToCopy)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(binding.root.context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
            }

            binding.btnWrongMeaning.setOnClickListener {
                onWrongMeaningClicked(item, position)
            }
        }
    }
}
