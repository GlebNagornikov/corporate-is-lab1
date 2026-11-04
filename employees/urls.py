from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, EmployeeViewSet

router = DefaultRouter()
router.register("employees", EmployeeViewSet)
router.register("departments", DepartmentViewSet)

urlpatterns = router.urls
