package org.kanglish.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Looper
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.overlay.FloatingSidebarService
import org.kanglish.app.ui.MainActivity
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowDialog
import org.robolectric.shadows.ShadowSettings

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33, 35])
class NotificationPermissionTest {
    private val app get() = RuntimeEnvironment.getApplication()

    @Before fun setup() {
        ShadowSettings.setCanDrawOverlays(true)
        shadowOf(app).denyPermissions(Manifest.permission.POST_NOTIFICATIONS)
        app.getSharedPreferences("notification_prefs", 0).edit().clear().commit()
    }

    @Test fun denialStillStartsTheBubbleAndDoesNotPromptAgain() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val activity = controller.get()
        assertNull(shadowOf(activity).lastRequestedPermission)
        activity.findViewById<View>(R.id.btnTestSidebar).performClick()
        val explanation = ShadowDialog.getLatestDialog() as AlertDialog
        assertTrue(explanation.findViewById<TextView>(android.R.id.message)!!.text.contains("still works"))
        explanation.getButton(AlertDialog.BUTTON_POSITIVE).performClick()
        shadowOf(Looper.getMainLooper()).idle()
        val request = shadowOf(activity).lastRequestedPermission
        assertArrayEquals(arrayOf(Manifest.permission.POST_NOTIFICATIONS), request.requestedPermissions)
        activity.onRequestPermissionsResult(request.requestCode, request.requestedPermissions, intArrayOf(PackageManager.PERMISSION_DENIED))
        assertEquals(FloatingSidebarService::class.java.name, shadowOf(app).nextStartedService.component?.className)
        assertEquals(activity.getString(R.string.bubble_notifications_off), activity.findViewById<TextView>(R.id.tvSidebarStatus).text)
        activity.findViewById<View>(R.id.btnTestSidebar).performClick()
        assertSame(request, shadowOf(activity).lastRequestedPermission)
        assertFalse(explanation.isShowing)
        controller.pause().stop().destroy()
    }

    @Test fun grantingNotificationsStartsTheBubble() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val activity = controller.get()
        activity.findViewById<View>(R.id.btnTestSidebar).performClick()
        (ShadowDialog.getLatestDialog() as AlertDialog).getButton(AlertDialog.BUTTON_POSITIVE).performClick()
        shadowOf(Looper.getMainLooper()).idle()
        val request = shadowOf(activity).lastRequestedPermission
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        activity.onRequestPermissionsResult(request.requestCode, request.requestedPermissions, intArrayOf(PackageManager.PERMISSION_GRANTED))
        assertEquals(FloatingSidebarService::class.java.name, shadowOf(app).nextStartedService.component?.className)
        assertEquals(activity.getString(R.string.bubble_active), activity.findViewById<TextView>(R.id.tvSidebarStatus).text)
        controller.pause().stop().destroy()
    }

    @Test fun notNowStartsTheBubbleWithoutRequestingPermission() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val activity = controller.get()
        activity.findViewById<View>(R.id.btnTestSidebar).performClick()
        (ShadowDialog.getLatestDialog() as AlertDialog).getButton(AlertDialog.BUTTON_NEGATIVE).performClick()
        shadowOf(Looper.getMainLooper()).idle()
        assertNull(shadowOf(activity).lastRequestedPermission)
        assertNotNull(shadowOf(app).nextStartedService)
        controller.pause().stop().destroy()
    }

    @Test @Config(sdk = [28]) fun android12AndEarlierDoNotRequestNotificationPermission() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        controller.get().findViewById<View>(R.id.btnTestSidebar).performClick()
        assertNull(shadowOf(controller.get()).lastRequestedPermission)
        assertNotNull(shadowOf(app).nextStartedService)
        controller.pause().stop().destroy()
    }
}
