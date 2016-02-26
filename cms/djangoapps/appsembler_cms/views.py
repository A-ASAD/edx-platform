import logging

from django.contrib.auth.models import User

from rest_framework import status

from cms.djangoapps.contentstore.utils import reverse_course_url
from cms.djangoapps.contentstore.views.course import create_new_course_in_store
from contentstore.utils import add_instructor
# from enrollment.api import add_enrollment
from opaque_keys.edx.keys import CourseKey
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from xmodule.modulestore import ModuleStoreEnum

from appsembler_lms.models import Organization
from appsembler_lms.permissions import SecretKeyPermission
from .serializers import CreateCourseSerializer

logger = logging.getLogger(__name__)
APPSEMBLER_EMAIL = 'support@appsembler.com'


class CreateCourseAPIView(GenericAPIView):
    permission_classes = (SecretKeyPermission,)
    serializer_class = CreateCourseSerializer

    def post(self, *args, **kwargs):
        serializer = self.get_serializer(data=self.request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.data.get('email'))
            except User.DoesNotExist:
                message = "User does not exist in academy.appsembler.com"
                return Response(status=status.HTTP_404_NOT_FOUND, data=message)

            store_for_new_course = modulestore().default_modulestore.get_modulestore_type()
            org = get_object_or_404(Organization, key=serializer.data.get('organization_key'))
            number = "{}101".format(user.username)
            run = "CurrentTerm"

            fields = {
                "display_name": "{}'s First Course".format(user.profile.name)
            }
            new_course = None
            logger.warning("===============================================================")
            if serializer.data.get('course_id'):
                course_id = serializer.data.get('course_id')
                try:
                    # with modulestore().default_store(ModuleStoreEnum.Type.split):
                    # this is here just so we know for sure whether it was cloned or not
                    # source_course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
                    destination_course_key = CourseKey.from_string("course-v1:{}+{}+{}".format(org.key, number, run))
                    logger.warning(destination_course_key)
                    number = "{}Clone".format(user.username)
                    new_course = modulestore().clone_course(source_course_id=course_id,
                                                            dest_course_id=destination_course_key,
                                                            user_id=user.username,
                                                            fields=fields)
                except Exception as e:
                    message = "Unable to clone course {}. {}".format(course_id, e)
                    logger.error(message)
                    logger.warning(e)

            if not new_course:
                try:
                    number = "{}101".format(user.username)
                    new_course = create_new_course_in_store(store_for_new_course, user, org.key,
                                                            number, run, fields)
                except Exception as e:
                    message = "Unable to create new course."
                    logger.error(message)
                    logger.warning(e)
                    return Response(status=status.HTTP_400_BAD_REQUEST)
            ## TODO: this must be removed before pushing to production
            ## requesting_user should be set to a valid academy.appsembler.com staff email address
            add_instructor(new_course.id, user, user)
            CourseEnrollment.enroll(user, new_course.id, mode='honor')
            new_course_url = reverse_course_url('course_handler', new_course.id)
            response_data = {
                'course_url': new_course_url,
            }
            return Response(status=status.HTTP_201_CREATED, data=response_data)

        return Response(status=status.HTTP_400_BAD_REQUEST)

create_course_endpoint = CreateCourseAPIView.as_view()
