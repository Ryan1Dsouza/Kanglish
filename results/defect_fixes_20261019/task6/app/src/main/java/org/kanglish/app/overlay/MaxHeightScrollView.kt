package org.kanglish.app.overlay

import android.content.Context
import android.util.AttributeSet
import android.widget.ScrollView

/** Wrap short overlay content; cap long content so the action row stays reachable. */
class MaxHeightScrollView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : ScrollView(context, attrs) {
    var maxHeightPx: Int = (200 * resources.displayMetrics.density).toInt()
        set(value) {
            field = value.coerceAtLeast(0)
            requestLayout()
        }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val parentLimit = if (MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.UNSPECIFIED) maxHeightPx
            else MeasureSpec.getSize(heightMeasureSpec)
        super.onMeasure(widthMeasureSpec, MeasureSpec.makeMeasureSpec(minOf(maxHeightPx, parentLimit), MeasureSpec.AT_MOST))
    }
}
